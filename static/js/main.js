// AI Recruiter Client side logic

document.addEventListener('DOMContentLoaded', function() {
    
    // ==========================================
    // 1. Drag & Drop File Upload Implementation
    // ==========================================
    const dragZone = document.getElementById('drag-zone');
    const fileInput = document.getElementById('resume-files');
    const fileListContainer = document.getElementById('file-list-container');
    
    if (dragZone && fileInput) {
        // Highlight drag area
        ['dragenter', 'dragover'].forEach(eventName => {
            dragZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dragZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dragZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                dragZone.classList.remove('dragover');
            }, false);
        });

        // Handle dropped files
        dragZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            // Transfer files to file input
            fileInput.files = files;
            updateFileList(files);
        });

        // Click zone to open browser file selector
        dragZone.addEventListener('click', () => {
            fileInput.click();
        });

        // Handle selected files from browser
        fileInput.addEventListener('change', () => {
            updateFileList(fileInput.files);
        });
    }

    function updateFileList(files) {
        if (!fileListContainer) return;
        fileListContainer.innerHTML = '';
        
        if (files.length === 0) {
            fileListContainer.innerHTML = '<span class="text-muted">No files selected</span>';
            return;
        }

        const list = document.createElement('div');
        list.className = 'd-flex flex-column gap-2 mt-3';

        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const sizeKB = (file.size / 1024).toFixed(1);
            
            const fileItem = document.createElement('div');
            fileItem.className = 'd-flex align-items-center justify-content-between p-3 rounded-3 border border-1 border-light-subtle bg-dark bg-opacity-25';
            fileItem.innerHTML = `
                <div class="d-flex align-items-center gap-2">
                    <i class="bi bi-file-earmark-pdf-fill text-danger fs-5"></i>
                    <div>
                        <div class="fw-bold">${file.name}</div>
                        <small class="text-muted">${sizeKB} KB</small>
                    </div>
                </div>
                <span class="badge bg-secondary">Pending</span>
            `;
            list.appendChild(fileItem);
        }
        fileListContainer.appendChild(list);
    }

    // ==========================================
    // 2. Animated Pipeline Stepper & Progress Bar
    // ==========================================
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const stepperItems = document.querySelectorAll('.step-item');
    const pipelineStatus = document.getElementById('pipeline-status');

    if (progressFill && progressPercent) {
        // Start AJAX pipeline ranking execution
        runPipeline();
    }

    function runPipeline() {
        let progress = 0;
        let activeStep = 0;
        
        // Simulative progress updates
        const interval = setInterval(() => {
            if (progress < 90) {
                progress += Math.floor(Math.random() * 4) + 1;
                updateProgressUI(progress);
                
                // Advance stepper based on thresholds
                if (progress > 15 && activeStep === 0) {
                    setStepState(0, 'completed');
                    setStepState(1, 'active');
                    activeStep = 1;
                } else if (progress > 40 && activeStep === 1) {
                    setStepState(1, 'completed');
                    setStepState(2, 'active');
                    activeStep = 2;
                } else if (progress > 65 && activeStep === 2) {
                    setStepState(2, 'completed');
                    setStepState(3, 'active');
                    activeStep = 3;
                } else if (progress > 85 && activeStep === 3) {
                    setStepState(3, 'completed');
                    setStepState(4, 'active');
                    activeStep = 4;
                }
            }
        }, 150);

        // Actual AJAX call to Flask backend
        fetch('/run_pipeline')
            .then(response => {
                if (!response.ok) {
                    throw new Error("Pipeline network error");
                }
                return response.json();
            })
            .then(data => {
                clearInterval(interval);
                // Complete everything
                updateProgressUI(100);
                stepperItems.forEach((item, idx) => setStepState(idx, 'completed'));
                
                if (pipelineStatus) {
                    pipelineStatus.innerText = "Ranking complete! Redirecting to results...";
                }
                
                // Delay redirect slightly for visual effect
                setTimeout(() => {
                    window.location.href = '/results';
                }, 800);
            })
            .catch(error => {
                clearInterval(interval);
                console.error("Pipeline failure:", error);
                
                if (progressFill) {
                    progressFill.style.background = 'var(--text-danger)';
                    progressFill.style.boxShadow = '0 0 15px var(--text-danger)';
                }
                if (pipelineStatus) {
                    pipelineStatus.innerHTML = `<span class="text-danger fw-bold"><i class="bi bi-exclamation-triangle-fill"></i> Pipeline Error: ${error.message}. Please reload and try again.</span>`;
                }
                setStepState(activeStep, 'completed');
                // Flag error state
                const currentStepItem = stepperItems[activeStep];
                if (currentStepItem) {
                    const icon = currentStepItem.querySelector('.step-icon');
                    if (icon) {
                        icon.style.borderColor = 'var(--text-danger)';
                        icon.style.color = 'var(--text-danger)';
                        icon.innerHTML = '<i class="bi bi-x-lg"></i>';
                    }
                }
            });
    }

    function updateProgressUI(pct) {
        if (progressFill) progressFill.style.width = pct + '%';
        if (progressPercent) progressPercent.innerText = pct + '%';
    }

    function setStepState(index, state) {
        const item = stepperItems[index];
        if (!item) return;

        if (state === 'active') {
            item.classList.add('active');
            item.classList.remove('completed');
            const icon = item.querySelector('.step-icon');
            if (icon && !icon.querySelector('.spinner-border')) {
                icon.innerHTML = '<div class="spinner-border spinner-border-sm text-info" role="status"><span class="visually-hidden">Loading...</span></div>';
            }
        } else if (state === 'completed') {
            item.classList.add('completed');
            item.classList.remove('active');
            const icon = item.querySelector('.step-icon');
            if (icon) {
                icon.style.boxShadow = 'none';
                icon.innerHTML = '<i class="bi bi-check-lg text-white"></i>';
            }
        }
    }

    // ==========================================
    // 3. Simple Client-Side Table Sorter
    // ==========================================
    const table = document.getElementById('results-table');
    if (table) {
        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(header => {
            header.addEventListener('click', () => {
                const colIdx = header.cellIndex;
                const isAscending = header.classList.contains('asc');
                
                // Clear directions on other columns
                headers.forEach(h => h.classList.remove('asc', 'desc'));
                
                // Toggle sorting direction
                header.classList.add(isAscending ? 'desc' : 'asc');
                
                sortTable(table, colIdx, !isAscending);
            });
        });
    }

    function sortTable(tableObj, columnIdx, asc) {
        const tbody = tableObj.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((rowA, rowB) => {
            const cellA = rowA.cells[columnIdx].innerText.trim();
            const cellB = rowB.cells[columnIdx].innerText.trim();
            
            // Try numeric comparison first
            const valA = parseFloat(cellA.replace('%', '').replace('Yrs', ''));
            const valB = parseFloat(cellB.replace('%', '').replace('Yrs', ''));
            
            if (!isNaN(valA) && !isNaN(valB)) {
                return asc ? valA - valB : valB - valA;
            }
            
            // Fallback to alphabetical
            return asc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
        });
        
        // Append sorted rows
        rows.forEach(row => tbody.appendChild(row));
    }
});
