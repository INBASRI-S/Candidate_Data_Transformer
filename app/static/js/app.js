document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const landingPage = document.getElementById("landing-page");
    const startAppBtn = document.getElementById("start-app-btn");
    const workspaceContainer = document.getElementById("workspace-container");
    const headerLogoBtn = document.getElementById("header-logo-btn");

    const form = document.getElementById("transform-form");
    const submitBtn = document.getElementById("submit-btn");
    const resetFormBtn = document.getElementById("reset-form-btn");
    const idleState = document.getElementById("idle-state");
    const resultsPanel = document.getElementById("results-panel");
    const resetResultsBtn = document.getElementById("reset-results-btn");
    const downloadBtn = document.getElementById("download-btn");
    const copyJsonBtn = document.getElementById("copy-json-btn");
    const clearLogsBtn = document.getElementById("clear-logs-btn");
    
    const profileName = document.getElementById("profile-name");
    const profileConfidence = document.getElementById("profile-confidence");
    const confidenceIconContainer = document.getElementById("confidence-icon-container");
    const jsonOutput = document.getElementById("json-output");
    const logsOutput = document.getElementById("logs-output");
    const configTextarea = document.getElementById("config_text");
    const configFile = document.getElementById("config_file");
    const configFileBadge = document.getElementById("config-file-badge");

    const candidateSelectorWrapper = document.getElementById("candidate-selector-wrapper");
    const candidateSelectDropdown = document.getElementById("candidate-select-dropdown");

    const toast = document.getElementById("toast");
    const modeStandardBtn = document.getElementById("mode-standard-btn");
    const modeCustomBtn = document.getElementById("mode-custom-btn");
    const customConfigContainer = document.getElementById("custom-config-container");

    // Tab Pane Controls
    const tabVisualBtn = document.getElementById("tab-visual-btn");
    const tabJsonBtn = document.getElementById("tab-json-btn");
    const tabLogsBtn = document.getElementById("tab-logs-btn");
    const paneVisual = document.getElementById("pane-visual");
    const paneJson = document.getElementById("pane-json");
    const paneLogs = document.getElementById("pane-logs");

    // Visual CV card components
    const profileAvatar = document.getElementById("profile-avatar");
    const profileDisplayName = document.getElementById("profile-display-name");
    const profileDisplayLocation = document.getElementById("profile-display-location");
    const visualContacts = document.getElementById("visual-contacts");
    const visualSkills = document.getElementById("visual-skills");
    const visualExperience = document.getElementById("visual-experience");
    const visualEducation = document.getElementById("visual-education");
    const widgetExperience = document.getElementById("widget-experience");
    const widgetEducation = document.getElementById("widget-education");

    // Visual Config Elements
    const checkboxes = document.querySelectorAll(".field-select-check");
    const renameInputs = document.querySelectorAll(".field-rename-input");
    const missingBehaviorSelect = document.getElementById("setting-missing-behavior");

    // File Preview Containers
    const resumeFileListContainer = document.getElementById("resume-file-list");
    const txtFileListContainer = document.getElementById("txt-file-list");

    // GitHub elements
    const githubUsernameInput = document.getElementById("github_username");
    const githubAddBtn = document.getElementById("github-add-btn");
    const githubTagsListContainer = document.getElementById("github-tags-list");

    // Global in-memory cache for candidate data (supports multiple candidates)
    let synthesizedCandidates = [];
    let activeCandidateIndex = 0;
    let latestCanonicalCandidate = null;
    let isCustomMode = false;

    // In-memory queues for multiple file uploads
    let selectedResumesList = [];
    let selectedNotesList = [];
    let selectedGithubList = [];

    // 1. Landing Page transitions
    startAppBtn.addEventListener("click", () => {
        landingPage.classList.add("fade-out-transition");
        setTimeout(() => {
            landingPage.style.display = "none";
            workspaceContainer.style.display = "flex";
            showToast("Workspace dashboard loaded", "success");
        }, 400);
    });

    headerLogoBtn.addEventListener("click", () => {
        workspaceContainer.style.display = "none";
        landingPage.style.display = "flex";
        landingPage.classList.remove("fade-out-transition");
    });

    // 2. Interactive Results Dashboard Tabs
    tabVisualBtn.addEventListener("click", () => {
        switchTab(tabVisualBtn, paneVisual);
    });
    tabJsonBtn.addEventListener("click", () => {
        switchTab(tabJsonBtn, paneJson);
    });
    tabLogsBtn.addEventListener("click", () => {
        switchTab(tabLogsBtn, paneLogs);
    });

    function switchTab(activeBtn, activePane) {
        [tabVisualBtn, tabJsonBtn, tabLogsBtn].forEach(btn => btn.classList.remove("active"));
        [paneVisual, paneJson, paneLogs].forEach(pane => pane.style.display = "none");
        
        activeBtn.classList.add("active");
        activePane.style.display = "block";
    }

    // 3. Visual Fields Config Selection Synchronization
    function syncVisualToConfigText() {
        const selectFields = [];
        const renameFields = {};
        
        checkboxes.forEach(chk => {
            if (chk.checked) {
                const field = chk.dataset.field;
                selectFields.push(field);
                
                // Get matching rename input
                const renameInput = document.querySelector(`.field-rename-input[data-field="${field}"]`);
                if (renameInput) {
                    const renameVal = renameInput.value.trim();
                    // If the user specified a custom alias rename target, track it
                    if (renameVal && renameVal !== field) {
                        renameFields[renameVal] = { "from": field };
                    }
                }
            }
        });
        
        const missingBehavior = missingBehaviorSelect.value;
        
        const configObj = {
            "select_fields": selectFields,
            "rename_fields": Object.keys(renameFields).length > 0 ? renameFields : null,
            "missing_field_behavior": missingBehavior,
            "include_confidence": selectFields.includes("overall_confidence"),
            "include_provenance": selectFields.includes("data_provenance")
        };
        
        configTextarea.value = JSON.stringify(configObj, null, 2);
    }

    function syncConfigTextToVisual(json) {
        // Uncheck all fields
        checkboxes.forEach(chk => chk.checked = false);
        
        // 1. Select fields
        const selectFields = json.select_fields || [];
        selectFields.forEach(field => {
            const chk = document.querySelector(`.field-select-check[data-field="${field}"]`);
            if (chk) chk.checked = true;
        });
        
        // 2. Rename fields (reset all values first)
        renameInputs.forEach(input => {
            const field = input.dataset.field;
            input.value = field;
        });
        
        const renameFields = json.rename_fields || {};
        for (const [renameVal, mapping] of Object.entries(renameFields)) {
            if (mapping && mapping.from) {
                const canonicalField = mapping.from;
                const renameInput = document.querySelector(`.field-rename-input[data-field="${canonicalField}"]`);
                if (renameInput) {
                    renameInput.value = renameVal;
                }
            }
        }
        
        // 3. Missing behavior select
        if (json.missing_field_behavior) {
            missingBehaviorSelect.value = json.missing_field_behavior;
        }
        
        // Final sync back to text
        syncVisualToConfigText();
    }

    // 4. Client-side Local Projection Algorithm
    function projectCandidateLocally(canonical, config) {
        let output = {};
        const selectFields = config.select_fields || [];
        const renameFields = config.rename_fields || {};
        const missingBehavior = config.missing_field_behavior || "null";
        
        selectFields.forEach(field => {
            let canonicalKey = field;
            // Map configuration checkbox key to canonical object property name
            if (field === "candidate_name") canonicalKey = "full_name";
            else if (field === "contact_emails") canonicalKey = "emails";
            else if (field === "contact_numbers") canonicalKey = "phones";
            else if (field === "data_provenance") canonicalKey = "provenance";
            
            let val = canonical[canonicalKey];
            
            // Check if value is missing/empty
            const isMissing = (val === undefined || val === null || (Array.isArray(val) && val.length === 0));
            
            if (isMissing) {
                if (missingBehavior === "omit") {
                    return; // skip adding to output
                } else if (missingBehavior === "error") {
                    val = "ERROR: Missing field";
                } else {
                    val = null;
                }
            }
            
            // Handle rename mappings
            let targetKey = field;
            if (renameFields) {
                for (const [renameVal, mapping] of Object.entries(renameFields)) {
                    if (mapping && mapping.from === field) {
                        targetKey = renameVal;
                        break;
                    }
                }
            }
            
            output[targetKey] = val;
        });
        
        return output;
    }

    // Main local sync coordinator
    function updateProjectedOutput() {
        if (!latestCanonicalCandidate) return;

        let projectedObj = {};
        if (isCustomMode) {
            syncVisualToConfigText();
            const configObj = JSON.parse(configTextarea.value);
            projectedObj = projectCandidateLocally(latestCanonicalCandidate, configObj);
        } else {
            // Standard mode: show full canonical candidate object
            projectedObj = { ...latestCanonicalCandidate };
            if (projectedObj.first_name === null) delete projectedObj.first_name;
            if (projectedObj.last_name === null) delete projectedObj.last_name;
        }

        // Update the cached projected_json for downloads
        if (synthesizedCandidates[activeCandidateIndex]) {
            synthesizedCandidates[activeCandidateIndex].projected_json = projectedObj;
        }

        // Render to Visual tab and JSON code tab
        renderVisualProfile(projectedObj);
        jsonOutput.textContent = JSON.stringify(projectedObj, null, 2);
    }

    // Bind event listeners for visual configuration changes to update output instantly
    checkboxes.forEach(chk => {
        chk.addEventListener("change", () => {
            const field = chk.dataset.field;
            const renameInput = document.querySelector(`.field-rename-input[data-field="${field}"]`);
            if (renameInput) {
                renameInput.disabled = !chk.checked;
            }
            syncVisualToConfigText();
            updateProjectedOutput();
        });
    });

    renameInputs.forEach(input => {
        input.addEventListener("input", () => {
            syncVisualToConfigText();
            updateProjectedOutput();
        });
    });

    missingBehaviorSelect.addEventListener("change", () => {
        syncVisualToConfigText();
        updateProjectedOutput();
    });

    // Run initial sync on load to populate default config state
    syncVisualToConfigText();

    // Toggle button handlers
    modeStandardBtn.addEventListener("click", () => {
        isCustomMode = false;
        modeStandardBtn.classList.add("active");
        modeCustomBtn.classList.remove("active");
        customConfigContainer.style.display = "none";
        showToast("Switched to Standard Output Mode", "success");
        updateProjectedOutput();
    });

    modeCustomBtn.addEventListener("click", () => {
        isCustomMode = true;
        modeCustomBtn.classList.add("active");
        modeStandardBtn.classList.remove("active");
        customConfigContainer.style.display = "block";
        showToast("Switched to Custom Projection Mode", "success");
        updateProjectedOutput();
    });

    // Handle Config File upload selection
    configFile.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (file) {
            configFileBadge.textContent = `Selected: ${file.name}`;
            configFileBadge.style.display = "inline-block";
            
            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const json = JSON.parse(event.target.result);
                    syncConfigTextToVisual(json);
                    showToast("Configuration loaded from file", "success");
                    updateProjectedOutput();
                } catch (err) {
                    showToast("Uploaded config is not valid JSON", "error");
                }
            };
            reader.readAsText(file);
        }
    });

    // Render interactive selected files list chips
    function renderFileList(type) {
        let container, list, dropzoneId, defaultText, iconClass;
        
        if (type === "resume") {
            container = resumeFileListContainer;
            list = selectedResumesList;
            dropzoneId = "drop-zone-resume";
            defaultText = "Drag PDF/DOCX here or browse";
            iconClass = "fa-file-pdf icon-pdf";
        } else {
            container = txtFileListContainer;
            list = selectedNotesList;
            dropzoneId = "drop-zone-txt";
            defaultText = "Drag TXT here or browse";
            iconClass = "fa-file-lines icon-txt";
        }
        
        const zone = document.getElementById(dropzoneId);
        const textSpan = zone.querySelector(".drop-zone-text");
        
        container.innerHTML = "";
        
        if (list.length === 0) {
            textSpan.textContent = defaultText;
            zone.classList.remove("drop-zone--selected");
            return;
        }
        
        // Update dropzone label to indicate you can add more files
        textSpan.textContent = `Selected ${list.length} file(s) - Add more`;
        zone.classList.add("drop-zone--selected");
        
        // Render chips
        list.forEach((file, index) => {
            const item = document.createElement("div");
            item.className = "file-chip-item";
            item.innerHTML = `
                <div class="file-chip-left">
                    <i class="fa-solid ${iconClass}"></i>
                    <span>${file.name}</span>
                </div>
                <button type="button" class="file-chip-remove" title="Remove File">&times;</button>
            `;
            
            item.querySelector(".file-chip-remove").addEventListener("click", (e) => {
                e.stopPropagation(); // prevent opening file browser dialog
                list.splice(index, 1);
                renderFileList(type);
                showToast(`Removed file: ${file.name}`, "info");
            });
            
            container.appendChild(item);
        });
    }

    // Initialize drag and drop dropzones
    const dropZones = [
        { id: "drop-zone-csv", inputId: "csv_file", defaultText: "Drag CSV here or browse" },
        { id: "drop-zone-resume", inputId: "resume_file", defaultText: "Drag PDF/DOCX here or browse" },
        { id: "drop-zone-txt", inputId: "txt_file", defaultText: "Drag TXT here or browse" }
    ];

    dropZones.forEach(({ id, inputId, defaultText }) => {
        const zone = document.getElementById(id);
        const input = document.getElementById(inputId);
        const textSpan = zone.querySelector(".drop-zone-text");

        // Click triggers input click
        zone.addEventListener("click", () => input.click());

        // Prevent event bubbling when clicking the input directly
        input.addEventListener("click", (e) => e.stopPropagation());

        // File selected
        input.addEventListener("change", () => {
            if (id === "drop-zone-csv") {
                // CSV remains single-file upload
                if (input.files.length > 0) {
                    textSpan.textContent = input.files[0].name;
                    zone.classList.add("drop-zone--selected");
                } else {
                    textSpan.textContent = defaultText;
                    zone.classList.remove("drop-zone--selected");
                }
            } else {
                // Resumes & Notes are appended sequentially to the list queue
                const type = id === "drop-zone-resume" ? "resume" : "txt";
                const targetList = id === "drop-zone-resume" ? selectedResumesList : selectedNotesList;
                
                Array.from(input.files).forEach(f => {
                    // Avoid inserting duplicate files by checking name and size
                    if (!targetList.some(item => item.name === f.name && item.size === f.size)) {
                        targetList.push(f);
                    }
                });
                
                // Clear input element value to allow re-selection of the same files later
                input.value = "";
                renderFileList(type);
            }
        });

        // Drag events
        zone.addEventListener("dragover", (e) => {
            e.preventDefault();
            zone.classList.add("drop-zone--dragover");
        });

        ["dragleave", "dragend"].forEach(type => {
            zone.addEventListener(type, () => {
                zone.classList.remove("drop-zone--dragover");
            });
        });

        zone.addEventListener("drop", (e) => {
            e.preventDefault();
            zone.classList.remove("drop-zone--dragover");
            
            if (e.dataTransfer.files.length > 0) {
                if (id === "drop-zone-csv") {
                    input.files = e.dataTransfer.files;
                    textSpan.textContent = input.files[0].name;
                    zone.classList.add("drop-zone--selected");
                } else {
                    const type = id === "drop-zone-resume" ? "resume" : "txt";
                    const targetList = id === "drop-zone-resume" ? selectedResumesList : selectedNotesList;
                    
                    Array.from(e.dataTransfer.files).forEach(f => {
                        if (!targetList.some(item => item.name === f.name && item.size === f.size)) {
                            targetList.push(f);
                        }
                    });
                    
                    renderFileList(type);
                }
            }
        });
    });

    // GitHub Tag queue handlers
    githubAddBtn.addEventListener("click", () => {
        addGithubTag();
    });

    githubUsernameInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            addGithubTag();
        }
    });

    function addGithubTag() {
        const val = githubUsernameInput.value.trim().replace(/,/g, "");
        if (!val) return;
        if (selectedGithubList.includes(val)) {
            showToast("GitHub profile already added", "info");
            githubUsernameInput.value = "";
            return;
        }
        selectedGithubList.push(val);
        githubUsernameInput.value = "";
        renderGithubTags();
    }

    function renderGithubTags() {
        githubTagsListContainer.innerHTML = "";
        selectedGithubList.forEach((username, index) => {
            const item = document.createElement("div");
            item.className = "file-chip-item";
            item.innerHTML = `
                <div class="file-chip-left">
                    <i class="fa-brands fa-github"></i>
                    <span>${username}</span>
                </div>
                <button type="button" class="file-chip-remove" title="Remove Profile">&times;</button>
            `;
            
            item.querySelector(".file-chip-remove").addEventListener("click", (e) => {
                e.stopPropagation();
                selectedGithubList.splice(index, 1);
                renderGithubTags();
                showToast(`Removed GitHub profile: ${username}`, "info");
            });
            
            githubTagsListContainer.appendChild(item);
        });
    }

    // Form submission
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        // Check if config JSON is valid before sending (only if custom mode is enabled)
        if (isCustomMode) {
            const configText = configTextarea.value.trim();
            if (configText) {
                try {
                    JSON.parse(configText);
                } catch (err) {
                    showToast("Invalid Configuration Settings!", "error");
                    return;
                }
            }
        }

        // Check if at least one file or GitHub username is provided
        const csvFile = document.getElementById("csv_file").files[0];

        if (!csvFile && selectedResumesList.length === 0 && selectedNotesList.length === 0 && selectedGithubList.length === 0) {
            showToast("Please provide at least one candidate source (Resume, Notes, CSV, or GitHub).", "error");
            return;
        }

        // Prepare Form Data
        const formData = new FormData(form);
        
        // Remove default form bounds of list inputs
        formData.delete("resume_file");
        formData.delete("txt_file");
        formData.delete("github_username");

        // Manually append files from our queues
        selectedResumesList.forEach(file => {
            formData.append("resume_file", file);
        });
        selectedNotesList.forEach(file => {
            formData.append("txt_file", file);
        });

        // Set compiled GitHub comma-separated usernames string
        if (selectedGithubList.length > 0) {
            formData.set("github_username", selectedGithubList.join(","));
        }

        // If Standard mode is selected, override custom config variables to send default empty configuration
        if (!isCustomMode) {
            formData.set("config_text", "{}");
            formData.delete("config_file");
        }

        // Update button state to loading
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin loading-pulse"></i> Processing...`;
        
        try {
            const response = await fetch("/transform", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            // Populate execution logs
            renderLogs(data.logs || []);

            if (response.ok && data.status === "success") {
                synthesizedCandidates = data.candidates || [];
                activeCandidateIndex = 0;
                
                if (synthesizedCandidates.length === 0) {
                    showToast("No candidates could be synthesized from inputs", "error");
                    return;
                }

                // Switch Right Panel from Idle State to active results panel
                idleState.style.display = "none";
                resultsPanel.style.display = "block";

                // Render Selector Bar dropdown
                renderCandidateSelector();

                // Load active candidate
                loadCandidateDetails(activeCandidateIndex);

                // Set Visual Profile tab active by default on load
                switchTab(tabVisualBtn, paneVisual);

                showToast(`Synthesized ${synthesizedCandidates.length} candidate profile(s) successfully!`, "success");
            } else {
                showToast(`Transformation failed: ${data.detail || "Server Error"}`, "error");
            }
        } catch (error) {
            console.error(error);
            showToast("Network connection error. Check server console.", "error");
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<i class="fa-solid fa-rotate-right"></i> Synthesize`;
        }
    });

    // Helper: Render candidate selector dropdown options
    function renderCandidateSelector() {
        candidateSelectDropdown.innerHTML = "";
        
        if (synthesizedCandidates.length <= 1) {
            candidateSelectorWrapper.style.display = "none";
            return;
        }
        
        candidateSelectorWrapper.style.display = "flex";
        synthesizedCandidates.forEach((cand, idx) => {
            const name = cand.canonical_candidate.full_name || `Candidate ${idx + 1}`;
            const option = document.createElement("option");
            option.value = idx;
            option.textContent = name;
            candidateSelectDropdown.appendChild(option);
        });
        
        candidateSelectDropdown.value = activeCandidateIndex;
    }

    // Dropdown change selector listener
    candidateSelectDropdown.addEventListener("change", (e) => {
        activeCandidateIndex = parseInt(e.target.value);
        loadCandidateDetails(activeCandidateIndex);
        
        const name = synthesizedCandidates[activeCandidateIndex].canonical_candidate.full_name || "candidate";
        showToast(`Switched profile to: ${name}`, "success");
    });

    // Helper: Load a candidate's cached canonical state
    function loadCandidateDetails(index) {
        if (!synthesizedCandidates[index]) return;
        
        currentCandidateId = synthesizedCandidates[index].candidate_id;
        latestCanonicalCandidate = synthesizedCandidates[index].canonical_candidate;
        
        // Compute and show projected outputs
        updateProjectedOutput();
    }

    // Dynamic Visual CV Profile Renderer
    function renderVisualProfile(json) {
        // 1. Candidate name & initials avatar
        const candidateName = json["candidate_name"] || json["full_name"] || json["name"] || "Candidate Profile";
        profileName.textContent = candidateName;
        profileDisplayName.textContent = candidateName;

        // Initials badge
        const nameParts = candidateName.split(/\s+/);
        let initials = "?";
        if (nameParts.length >= 2) {
            initials = (nameParts[0][0] + nameParts[nameParts.length - 1][0]).toUpperCase();
        } else if (nameParts.length === 1 && nameParts[0].length > 0) {
            initials = nameParts[0].substring(0, 2).toUpperCase();
        }
        profileAvatar.textContent = initials;

        // 2. Candidate Location
        const countryVal = json["country"] || json["location"] || "-";
        profileDisplayLocation.innerHTML = `<i class="fa-solid fa-location-dot"></i> ${countryVal}`;

        // 3. Confidence Rating
        const confidenceVal = json["overall_confidence"] !== undefined ? json["overall_confidence"] : 
                              (json["confidence"] !== undefined ? json["confidence"] : json["confidence_rating"]);
        if (confidenceVal !== undefined) {
            const percentage = Math.round(parseFloat(confidenceVal) * 100);
            profileConfidence.textContent = `${percentage}%`;
            
            if (percentage >= 85) {
                confidenceIconContainer.innerHTML = `<i class="fa-solid fa-shield-halved text-success"></i>`;
            } else if (percentage >= 70) {
                confidenceIconContainer.innerHTML = `<i class="fa-solid fa-gauge-high text-warning"></i>`;
            } else {
                confidenceIconContainer.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-error" style="color:var(--error)"></i>`;
            }
        } else {
            profileConfidence.textContent = "N/A";
            confidenceIconContainer.innerHTML = `<i class="fa-solid fa-ban text-muted"></i>`;
        }

        // 4. Contact Details Column
        visualContacts.innerHTML = "";
        const emailList = json["contact_emails"] || json["emails"] || (json["email"] ? [json["email"]] : []);
        const phoneList = json["contact_numbers"] || json["phones"] || (json["phone"] ? [json["phone"]] : []);

        const emails = Array.isArray(emailList) ? emailList : [emailList];
        const phones = Array.isArray(phoneList) ? phoneList : [phoneList];

        emails.forEach(email => {
            if (email && email.trim()) {
                const item = document.createElement("div");
                item.className = "contact-item";
                item.innerHTML = `<i class="fa-solid fa-envelope"></i> <span>${email}</span>`;
                visualContacts.appendChild(item);
            }
        });

        phones.forEach(phone => {
            if (phone && phone.trim()) {
                const item = document.createElement("div");
                item.className = "contact-item";
                item.innerHTML = `<i class="fa-solid fa-phone"></i> <span>${phone}</span>`;
                visualContacts.appendChild(item);
            }
        });

        if (visualContacts.children.length === 0) {
            visualContacts.innerHTML = `<span class="text-muted" style="font-size:0.8rem">No contact info</span>`;
        }

        // 5. Skills pills wrap
        visualSkills.innerHTML = "";
        const skillList = json["skills"] || json["technical_skills"] || [];
        const skills = Array.isArray(skillList) ? skillList : [skillList];

        skills.forEach(skill => {
            if (skill && skill.trim()) {
                const pill = document.createElement("span");
                pill.className = "skill-pill";
                pill.textContent = skill;
                visualSkills.appendChild(pill);
            }
        });

        if (visualSkills.children.length === 0) {
            visualSkills.innerHTML = `<span class="text-muted" style="font-size:0.8rem">No skills extracted</span>`;
        }

        // 6. Experience Timeline
        visualExperience.innerHTML = "";
        const expList = json["experience"] || json["work_history"] || [];
        const experiences = Array.isArray(expList) ? expList : [];

        if (experiences.length > 0) {
            widgetExperience.style.display = "flex";
            experiences.forEach(exp => {
                const company = exp["company"] || exp["employer"] || "-";
                const title = exp["title"] || exp["job_title"] || exp["role"] || "Software Engineer";
                const start = exp["start_date"] || "-";
                const end = exp["end_date"] || "Present";
                const desc = exp["description"] || "";

                const entry = document.createElement("div");
                entry.className = "timeline-entry";
                entry.innerHTML = `
                    <div class="timeline-node"></div>
                    <div class="timeline-header">
                        <h5>${title}</h5>
                        <span class="timeline-company">${company}</span>
                        <span class="timeline-date">${start} - ${end}</span>
                    </div>
                    ${desc ? `<p class="timeline-desc">${desc}</p>` : ''}
                `;
                visualExperience.appendChild(entry);
            });
        } else {
            widgetExperience.style.display = "none";
        }

        // 7. Education Cards list
        visualEducation.innerHTML = "";
        const eduList = json["education"] || json["studies"] || [];
        const educations = Array.isArray(eduList) ? eduList : [];

        if (educations.length > 0) {
            widgetEducation.style.display = "flex";
            educations.forEach(edu => {
                const school = edu["institution"] || edu["school"] || edu["university"] || "-";
                const degree = edu["degree"] || "-";
                const field = edu["field_of_study"] || edu["major"] || "";
                const start = edu["start_date"] || "";
                const end = edu["end_date"] || "";

                let degreeText = degree;
                if (field) degreeText += ` in ${field}`;

                let dateText = "";
                if (start && end) dateText = `${start} - ${end}`;
                else if (end) dateText = end;

                const card = document.createElement("div");
                card.className = "edu-entry-card";
                card.innerHTML = `
                    <h5 class="edu-school">${school}</h5>
                    <span class="edu-degree">${degreeText}</span>
                    ${dateText ? `<div class="edu-date">${dateText}</div>` : ''}
                `;
                visualEducation.appendChild(card);
            });
        } else {
            widgetEducation.style.display = "none";
        }
    }

    // Reset Form button handler
    resetFormBtn.addEventListener("click", () => {
        form.reset();
        
        // Reset Dropzone UI states
        dropZones.forEach(({ id, defaultText }) => {
            const zone = document.getElementById(id);
            const textSpan = zone.querySelector(".drop-zone-text");
            textSpan.textContent = defaultText;
            zone.classList.remove("drop-zone--selected");
            zone.classList.remove("drop-zone--dragover");
        });

        // Reset file queue lists & lists container
        selectedResumesList = [];
        selectedNotesList = [];
        selectedGithubList = [];
        resumeFileListContainer.innerHTML = "";
        txtFileListContainer.innerHTML = "";
        githubTagsListContainer.innerHTML = "";

        // Reset output mode to Standard
        isCustomMode = false;
        modeStandardBtn.classList.add("active");
        modeCustomBtn.classList.remove("active");
        customConfigContainer.style.display = "none";

        // Reset check boxes to checked
        checkboxes.forEach(chk => {
            chk.checked = true;
            const renameInput = document.querySelector(`.field-rename-input[data-field="${chk.dataset.field}"]`);
            if (renameInput) {
                renameInput.disabled = false;
                renameInput.value = chk.dataset.field;
            }
        });
        missingBehaviorSelect.value = "null";

        // Clear file badge
        configFileBadge.style.display = "none";
        syncVisualToConfigText();

        // Switch Right Panel back to Idle State
        resultsPanel.style.display = "none";
        idleState.style.display = "flex";
        jsonOutput.textContent = "";
        logsOutput.innerHTML = "";
        currentCandidateId = null;
        latestCanonicalCandidate = null;
        synthesizedCandidates = [];
        activeCandidateIndex = 0;
        candidateSelectDropdown.innerHTML = "";
        candidateSelectorWrapper.style.display = "none";

        showToast("Inputs, configuration, and dashboard reset", "success");
    });

    // Reset Results panel button handler
    resetResultsBtn.addEventListener("click", () => {
        resultsPanel.style.display = "none";
        idleState.style.display = "flex";
        jsonOutput.textContent = "";
        logsOutput.innerHTML = "";
        currentCandidateId = null;
        latestCanonicalCandidate = null;
        synthesizedCandidates = [];
        activeCandidateIndex = 0;
        candidateSelectDropdown.innerHTML = "";
        candidateSelectorWrapper.style.display = "none";
        showToast("Dashboard output reset", "success");
    });

    // Download dynamic JSON output file (from displayed state)
    downloadBtn.addEventListener("click", () => {
        const jsonText = jsonOutput.textContent;
        if (jsonText) {
            const blob = new Blob([jsonText], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            const name = profileDisplayName.textContent.trim().replace(/\s+/g, "_") || "candidate";
            a.href = url;
            a.download = `${name}_profile.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast("Downloaded updated JSON output file", "success");
        } else {
            showToast("No active candidate JSON output to download", "error");
        }
    });

    // Copy JSON to clipboard
    copyJsonBtn.addEventListener("click", () => {
        const text = jsonOutput.textContent;
        if (text) {
            navigator.clipboard.writeText(text).then(() => {
                showToast("Copied JSON output to clipboard", "success");
            }).catch(err => {
                showToast("Failed to copy text", "error");
            });
        }
    });

    // Clear execution logs
    clearLogsBtn.addEventListener("click", () => {
        logsOutput.innerHTML = "";
        showToast("Console cleared", "success");
    });

    // Render Logs Helper
    function renderLogs(logsList) {
        logsOutput.innerHTML = "";
        if (logsList.length === 0) {
            logsOutput.innerHTML = `<div class="log-line log-line-debug">> No execution logs recorded.</div>`;
            return;
        }

        logsList.forEach(log => {
            const logLine = document.createElement("div");
            logLine.className = "log-line";
            
            // Format log based on contents
            if (log.includes("INFO")) {
                logLine.classList.add("log-line-info");
            } else if (log.includes("WARNING")) {
                logLine.classList.add("log-line-warning");
            } else if (log.includes("ERROR")) {
                logLine.classList.add("log-line-error");
            } else {
                logLine.classList.add("log-line-debug");
            }
            
            logLine.textContent = log;
            logsOutput.appendChild(logLine);
        });

        // Auto Scroll logs terminal to bottom
        logsOutput.scrollTop = logsOutput.scrollHeight;
    }

    // Show toast notifications helper
    function showToast(message, type = "success") {
        toast.className = `toast show toast-${type}`;
        
        const icon = type === "success" 
            ? `<i class="fa-solid fa-circle-check" style="color:var(--success)"></i>` 
            : `<i class="fa-solid fa-triangle-exclamation" style="color:var(--error)"></i>`;
            
        toast.innerHTML = `${icon} <span>${message}</span>`;

        // Clear previous timeout if any
        if (window.toastTimeout) {
            clearTimeout(window.toastTimeout);
        }

        window.toastTimeout = setTimeout(() => {
            toast.classList.remove("show");
        }, 3500);
    }
});
