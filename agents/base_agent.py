"""
Shared base class for all three agents. Owns the actual LLM API call,
retry-on-API-error logic, and logging — so Mathematician/Architect/Adversary
only need to define their prompt + how to parse the response.
"""

import os
import time
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AgentCallLog:
    agent_name: str
    system_prompt: str
    user_message: str
    raw_response: str
    model: str
    duration_seconds: float = 0.0


class BaseAgent(ABC):
    """
    Shared base class for all three agents. Handles Anthropic and Google Gemini API communication,
    transient retry logic, and transaction logging.
    """

    agent_name: str

    def __init__(self, model: str, prompts_dir: Path):
        self.model = model
        self.prompts_dir = prompts_dir
        
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if gemini_key or "gemini" in model.lower():
            from google import genai
            self.provider = "gemini"
            self.client = genai.Client(api_key=gemini_key or "mock_key_for_testing")
        else:
            import anthropic
            self.provider = "anthropic"
            api_key = os.environ.get("ANTHROPIC_API_KEY", "mock_key_for_testing")
            self.client = anthropic.Anthropic(api_key=api_key)

    @abstractmethod
    def system_prompt_filename(self) -> str:
        ...

    def load_system_prompt(self) -> str:
        path = self.prompts_dir / self.system_prompt_filename()
        return path.read_text()

    def call(self, user_message: str, run_id: str = "default") -> str:
        """
        Call the appropriate LLM API with transient retry logic.
        """
        system_prompt = self.load_system_prompt()
        
        max_retries = 10
        backoff = 2.0
        
        for attempt in range(max_retries):
            try:
                # Add natural rate limiting throttle (3 seconds delay) for Gemini free tier
                if self.provider == "gemini":
                    time.sleep(3.0)
                    
                start_time = time.perf_counter()
                
                if self.provider == "gemini":
                    from google.genai import types
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=user_message,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            max_output_tokens=4000
                        )
                    )
                    raw_response = response.text or ""
                else:
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=4000,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": user_message}
                        ]
                    )
                    raw_response = ""
                    for block in response.content:
                        if block.type == "text":
                            raw_response += block.text
                
                duration = time.perf_counter() - start_time
                self.log_call(run_id, user_message, raw_response, duration)
                return raw_response
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                
                error_str = str(e).lower()
                if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
                    import logging
                    import re
                    logger = logging.getLogger("agents.base")
                    
                    sleep_time = 15 * (attempt + 1)
                    match_msg = re.search(r"please\s+retry\s+in\s+([\d\.]+)\s*s", error_str)
                    match_delay = re.search(r"retrydelay':\s*'(\d+)s", error_str)
                    
                    if match_msg:
                        try:
                            sleep_time = int(float(match_msg.group(1))) + 2
                        except ValueError:
                            pass
                    elif match_delay:
                        try:
                            sleep_time = int(match_delay.group(1)) + 2
                        except ValueError:
                            pass
                            
                    logger.warning(f"Rate limit hit: {e}. Sleeping for {sleep_time}s to reset quota (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(sleep_time)
                else:
                    time.sleep(backoff ** attempt)
        return ""

    def log_call(self, run_id: str, user_message: str, raw_response: str, duration_seconds: float):
        """
        Logs the agent call to the runs directory in JSONL format.
        """
        from config.settings import settings
        
        log_dir = settings.paths.logs_dir / run_id
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_entry = AgentCallLog(
            agent_name=self.agent_name,
            system_prompt=self.load_system_prompt(),
            user_message=user_message,
            raw_response=raw_response,
            model=self.model,
            duration_seconds=duration_seconds
        )
        
        log_file = log_dir / "agent_calls.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(log_entry)) + "\n")
