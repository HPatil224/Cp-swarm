document.addEventListener('DOMContentLoaded', () => {
    // State
    let selectedProblem = null;
    let activeRunId = null;
    let socket = null;
    
    // UI Elements
    const problemsList = document.getElementById('problems-list');
    const runsList = document.getElementById('runs-list');
    const activeTitle = document.getElementById('active-title');
    const categoryBadge = document.getElementById('category-badge');
    const btnRunSolver = document.getElementById('btn-run-solver');
    
    const welcomeView = document.getElementById('welcome-view');
    const customFormView = document.getElementById('custom-form-view');
    const runView = document.getElementById('run-view');
    
    // Stepper
    const stepMath = document.getElementById('step-math');
    const stepArch = document.getElementById('step-arch');
    const stepAdv = document.getElementById('step-adv');
    
    // Cards
    const cardMath = document.getElementById('card-mathematician');
    const cardArch = document.getElementById('card-architect');
    const cardAdv = document.getElementById('card-adversary');
    const termConsole = document.getElementById('terminal-console');
    
    // Custom Problem
    const btnCustomProblem = document.getElementById('btn-custom-problem');
    const btnCancelCustom = document.getElementById('btn-cancel-custom');
    const customForm = document.getElementById('custom-problem-form');
    const samplesContainer = document.getElementById('samples-container');
    const btnAddSample = document.getElementById('btn-add-sample');
    
    // Initial Load
    loadProblems();
    loadRuns();
    
    // Add Event Listeners
    btnCustomProblem.addEventListener('click', showCustomForm);
    btnCancelCustom.addEventListener('click', hideCustomForm);
    btnAddSample.addEventListener('click', addSampleRow);
    customForm.addEventListener('submit', handleCustomSubmit);
    btnRunSolver.addEventListener('click', triggerSolver);
    document.getElementById('btn-copy-cpp').addEventListener('click', copyCPPCode);
    
    // Functions
    async function loadProblems() {
        try {
            const res = await fetch('/api/problems');
            const data = await res.json();
            problemsList.innerHTML = '';
            
            if (data.length === 0) {
                problemsList.innerHTML = '<li class="loading-item">No problems found</li>';
                return;
            }
            
            data.forEach(p => {
                const li = document.createElement('li');
                li.textContent = p.title;
                li.title = p.title;
                li.addEventListener('click', () => selectProblem(p, li));
                problemsList.appendChild(li);
            });
        } catch (e) {
            console.error(e);
            problemsList.innerHTML = '<li class="loading-item">Failed to load problems</li>';
        }
    }
    
    async function loadRuns() {
        try {
            const res = await fetch('/api/runs');
            const data = await res.json();
            runsList.innerHTML = '';
            
            if (data.length === 0) {
                runsList.innerHTML = '<li class="loading-item">No historical runs</li>';
                return;
            }
            
            data.forEach(r => {
                const li = document.createElement('li');
                li.innerHTML = `${r.title} <small style="display:block;color:#6b7280;font-size:11px;">ID: ${r.run_id} | ${r.status}</small>`;
                li.addEventListener('click', () => selectRun(r.run_id));
                runsList.appendChild(li);
            });
        } catch (e) {
            console.error(e);
            runsList.innerHTML = '<li class="loading-item">Failed to load history</li>';
        }
    }
    
    function selectProblem(prob, element) {
        selectedProblem = prob;
        activeRunId = null;
        
        // Update active class in sidebar
        document.querySelectorAll('#problems-list li').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('#runs-list li').forEach(el => el.classList.remove('active'));
        element.classList.add('active');
        
        // Update headers
        activeTitle.textContent = prob.title;
        categoryBadge.textContent = prob.category.toUpperCase();
        btnRunSolver.disabled = false;
        
        // Switch view to welcome view and clear previous run views
        hideAllViews();
        welcomeView.classList.remove('hidden');
    }
    
    async function selectRun(runId) {
        hideAllViews();
        runView.classList.remove('hidden');
        
        // Highlight run list item
        document.querySelectorAll('#problems-list li').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('#runs-list li').forEach(el => el.classList.remove('active'));
        
        // Reset console
        termConsole.innerHTML = `<p class="log-line system">[System] Loading historical run logs for ${runId}...</p>`;
        
        try {
            const res = await fetch(`/api/runs/${runId}`);
            const data = await res.json();
            
            activeTitle.textContent = `Historical Run ${runId}`;
            categoryBadge.textContent = "HISTORY";
            btnRunSolver.disabled = true;
            
            // Render transcript in console
            termConsole.innerHTML = '';
            const lines = data.transcript.split('\n');
            lines.forEach(l => {
                if (l.trim()) {
                    appendConsoleLine(l, 'system');
                }
            });
            
            // Show code card
            if (data.solution) {
                cardArch.classList.remove('hidden');
                document.getElementById('code-cpp').textContent = data.solution;
                document.getElementById('code-notes').textContent = "Recovered from saved C++ solution.";
                document.getElementById('code-version-badge').textContent = "FINAL";
            }
        } catch (e) {
            appendConsoleLine(`Error loading historical details: ${e}`, 'error');
        }
    }
    
    function showCustomForm() {
        hideAllViews();
        customFormView.classList.remove('hidden');
        activeTitle.textContent = "Submit Custom CP Problem";
        categoryBadge.textContent = "CUSTOM";
        btnRunSolver.disabled = true;
        
        // Remove active highlights
        document.querySelectorAll('#problems-list li').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('#runs-list li').forEach(el => el.classList.remove('active'));
    }
    
    function hideCustomForm() {
        hideAllViews();
        welcomeView.classList.remove('hidden');
        activeTitle.textContent = "Select a problem to start";
        categoryBadge.textContent = "BENCHMARKS";
    }
    
    function hideAllViews() {
        welcomeView.classList.add('hidden');
        customFormView.classList.add('hidden');
        runView.classList.add('hidden');
        cardMath.classList.add('hidden');
        cardArch.classList.add('hidden');
        cardAdv.classList.add('hidden');
    }
    
    function addSampleRow() {
        const div = document.createElement('div');
        div.className = 'sample-pair';
        div.innerHTML = `
            <div class="sub-group">
                <label>Input</label>
                <textarea class="sample-input" required placeholder="Paste test case input..."></textarea>
            </div>
            <div class="sub-group">
                <label>Expected Output</label>
                <textarea class="sample-output" required placeholder="Expected output..."></textarea>
            </div>
        `;
        samplesContainer.appendChild(div);
    }
    
    async function handleCustomSubmit(e) {
        e.preventDefault();
        
        const title = document.getElementById('custom-title').value;
        const statement = document.getElementById('custom-statement').value;
        
        const sampleInputs = document.querySelectorAll('.sample-input');
        const sampleOutputs = document.querySelectorAll('.sample-output');
        const samples = [];
        
        for (let i = 0; i < sampleInputs.length; i++) {
            samples.push({
                input: sampleInputs[i].value,
                output: sampleOutputs[i].value
            });
        }
        
        selectedProblem = {
            title: title,
            statement: statement,
            samples: samples,
            isCustom: true
        };
        
        activeTitle.textContent = title;
        categoryBadge.textContent = "CUSTOM";
        
        // Start solve directly
        await triggerSolver();
    }
    
    async function triggerSolver() {
        if (!selectedProblem) return;
        
        hideAllViews();
        runView.classList.remove('hidden');
        btnRunSolver.disabled = true;
        
        // Reset Stepper
        document.querySelectorAll('.step').forEach(el => {
            el.className = 'step';
        });
        
        termConsole.innerHTML = '<p class="log-line system">[System] Contacting backend, starting solving pipeline...</p>';
        
        // Construct payload
        const payload = {};
        if (selectedProblem.isCustom) {
            payload.custom_problem = {
                title: selectedProblem.title,
                statement: selectedProblem.statement,
                samples: selectedProblem.samples
            };
        } else {
            payload.file_path = selectedProblem.filepath;
        }
        
        try {
            const res = await fetch('/api/solve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.status === 'started') {
                activeRunId = data.run_id;
                connectWebSocket(data.run_id);
            } else {
                appendConsoleLine("Failed to initiate solver: pipeline solve did not return started.", 'error');
                btnRunSolver.disabled = false;
            }
        } catch (e) {
            appendConsoleLine(`Connection error starting solver: ${e}`, 'error');
            btnRunSolver.disabled = false;
        }
    }
    
    function connectWebSocket(runId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/solve/${runId}`;
        
        socket = new WebSocket(wsUrl);
        
        socket.onopen = () => {
            appendConsoleLine(`[System] WebSocket stream established for session ID: ${runId}`, 'system');
        };
        
        socket.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleSolveEvent(msg.event, msg.data);
        };
        
        socket.onclose = () => {
            appendConsoleLine('[System] WebSocket stream closed.', 'system');
            btnRunSolver.disabled = false;
            loadRuns(); // Reload history pane
        };
        
        socket.onerror = (e) => {
            appendConsoleLine(`[System] WebSocket error occurred: ${e}`, 'error');
        };
    }
    
    function handleSolveEvent(event, data) {
        switch (event) {
            case 'run_start':
                appendConsoleLine(`[System] Starting loop run for problem: ${data.problem_title}`, 'system');
                break;
                
            case 'mathematician_start':
                setStepActive(stepMath);
                appendConsoleLine('[Mathematician] Analyzing problem statements and math constraints...', 'math');
                break;
                
            case 'mathematician_end':
                setStepCompleted(stepMath);
                cardMath.classList.remove('hidden');
                document.getElementById('math-pattern').textContent = `${data.pattern} Complexity Budget: ${data.complexity_bound}`;
                document.getElementById('math-justification').textContent = data.justification;
                document.getElementById('math-pseudocode').textContent = data.pseudocode;
                appendConsoleLine(`[Mathematician] Structured algorithmic approach: Pattern: ${data.pattern}, Complexity: ${data.complexity_bound}`, 'math');
                break;
                
            case 'architect_start':
                setStepActive(stepArch);
                appendConsoleLine(`[Architect] Coding C++ Implementation version attempt ${data.attempt}...`, 'arch');
                break;
                
            case 'architect_end':
                setStepCompleted(stepArch);
                cardArch.classList.remove('hidden');
                
                if (data.disputes) {
                    document.getElementById('code-cpp').textContent = `// Architect disputed the approach:\n// ${data.dispute_reason}`;
                    document.getElementById('code-notes').textContent = `Disputed: ${data.dispute_reason}`;
                    appendConsoleLine(`[Architect] Disputed proposed mathematical approach: ${data.dispute_reason}`, 'error');
                } else {
                    document.getElementById('code-cpp').textContent = data.source_code;
                    document.getElementById('code-notes').textContent = data.notes || "none";
                    appendConsoleLine(`[Architect] C++ source code generated successfully.`, 'arch');
                }
                break;
                
            case 'adversary_start':
                setStepActive(stepAdv);
                appendConsoleLine('[Adversary] Compiling code and executing stress tests in sandbox...', 'adv');
                break;
                
            case 'adversary_end':
                cardAdv.classList.remove('hidden');
                const summaryDiv = document.getElementById('adv-summary');
                const errPanel = document.getElementById('adv-error-panel');
                
                if (data.failure_type === 'none') {
                    setStepCompleted(stepAdv);
                    summaryDiv.className = 'status-summary solved';
                    summaryDiv.textContent = 'Correctness check passed: All stress tests successfully completed!';
                    errPanel.classList.add('hidden');
                    appendConsoleLine('[Adversary] Clean execution check: All tests successfully passed!', 'success');
                } else {
                    summaryDiv.className = 'status-summary failed';
                    summaryDiv.textContent = `Correctness check failed: Detected code-level issue [${data.failure_type.toUpperCase()}]`;
                    appendConsoleLine(`[Adversary] Correctness check failed: ${data.failure_type.toUpperCase()}. Detail: ${data.notes}`, 'error');
                    
                    if (data.failing_test) {
                        errPanel.classList.remove('hidden');
                        document.getElementById('adv-failing-hypothesis').textContent = data.failing_test.hypothesis;
                        document.getElementById('adv-failing-input').textContent = data.failing_test.input;
                        document.getElementById('adv-failing-expected').textContent = data.failing_test.expected || 'unknown (run refer)';
                        document.getElementById('adv-failing-actual').textContent = data.actual_output || 'none';
                    } else {
                        errPanel.classList.add('hidden');
                    }
                }
                break;
                
            case 'solved':
                appendConsoleLine('[System] SOLVED: Swarm solver completed successfully!', 'success');
                break;
                
            case 'failed':
                appendConsoleLine(`[System] FAILED: Solver loop aborted. Reason: ${data.status}`, 'error');
                break;
        }
    }
    
    function setStepActive(stepEl) {
        stepEl.classList.remove('completed');
        stepEl.classList.add('active');
    }
    
    function setStepCompleted(stepEl) {
        stepEl.classList.remove('active');
        stepEl.classList.add('completed');
    }
    
    function appendConsoleLine(text, className) {
        const p = document.createElement('p');
        p.className = `log-line ${className}`;
        p.textContent = text;
        termConsole.appendChild(p);
        termConsole.scrollTop = termConsole.scrollHeight;
    }
    
    function copyCPPCode() {
        const codeText = document.getElementById('code-cpp').textContent;
        navigator.clipboard.writeText(codeText).then(() => {
            const btn = document.getElementById('btn-copy-cpp');
            btn.textContent = 'Copied!';
            setTimeout(() => {
                btn.textContent = 'Copy Code';
            }, 2000);
        });
    }
});
