(function () {
    'use strict';

    function init() {
        var page = document.getElementById('task-detail-page');
        if (!page) {
            return;
        }

        var taskId = parseInt(page.dataset.taskId, 10);
        if (!taskId) {
            return;
        }

        var uploadForm = document.getElementById('solution-upload-form');
        var fileInput = document.getElementById('task-file');
        var submitBtn = document.getElementById('submit-task-file');
        var selectedFileName = document.getElementById('selected-file-name');
        var uploadStatus = document.getElementById('upload-status');
        var solutionSection = document.getElementById('solution-section');
        var solutionText = document.getElementById('solution-text');
        var progressBadge = document.getElementById('progress-status-badge');
        var preUploadActions = document.getElementById('pre-upload-actions');
        var postUploadActions = document.getElementById('post-upload-actions');
        var uploadedFileLink = document.getElementById('uploaded-file-link');
        var openSolutionBtn = document.getElementById('open-solution-btn');
        var taskFilePicker = document.getElementById('task-file-picker');

        var state = {
            solved: page.dataset.solved === 'true',
            busy: false
        };

        function normalizeUrlPath(value) {
            return (value || '').replace(/\\/g, '/');
        }

        function isImageFile(name) {
            return /\.(png|jpe?g|gif|webp|svg)$/i.test(name || '');
        }

        function setBusy(value) {
            state.busy = value;
            if (submitBtn) {
                submitBtn.disabled = value || (!fileInput || !fileInput.files || !fileInput.files.length);
                submitBtn.textContent = value ? 'Отправляем...' : 'Отправить файл';
            }
            if (fileInput) {
                fileInput.disabled = value;
            }
        }

        function showSolution(solution) {
            if (solutionSection) {
                solutionSection.hidden = false;
            }
            if (solutionText && typeof solution === 'string') {
                solutionText.textContent = solution;
            }
        }

        function showPostUploadActions(fileName, fileUrl) {
            if (preUploadActions) {
                preUploadActions.hidden = true;
            }
            if (postUploadActions) {
                postUploadActions.hidden = false;
            }
            if (uploadedFileLink) {
                uploadedFileLink.href = fileUrl || '#';
                uploadedFileLink.setAttribute('aria-disabled', fileUrl ? 'false' : 'true');
                uploadedFileLink.tabIndex = fileUrl ? 0 : -1;
                uploadedFileLink.textContent = fileName ? ('Открыть файл: ' + fileName) : 'Открыть отправленный файл';
            }
        }

        function showUploadedFile(fileName, fileUrl) {
            if (taskFilePicker) {
                taskFilePicker.hidden = true;
                taskFilePicker.style.display = 'none';
            }

            if (selectedFileName) {
                selectedFileName.textContent = fileName || 'Файл отправлен';
            }

            if (uploadedFileLink) {
                uploadedFileLink.href = normalizeUrlPath(fileUrl || uploadedFileLink.href || '#');
                uploadedFileLink.textContent = fileName ? ('Открыть файл: ' + fileName) : 'Открыть отправленный файл';
                uploadedFileLink.setAttribute('aria-disabled', fileUrl ? 'false' : 'true');
                uploadedFileLink.tabIndex = fileUrl ? 0 : -1;
            }
        }

        function unlockSolution(data) {
            state.solved = true;

            if (progressBadge) {
                progressBadge.textContent = 'Файл отправлен';
                progressBadge.className = 'task-status-chip is-solved';
            }

            var uploadedName = data.file_name || (fileInput && fileInput.files[0] && fileInput.files[0].name) || 'Файл';
            var uploadedUrl = normalizeUrlPath(data.file_url || data.submission_file_url || data.submission_file_path || '');

            showUploadedFile(uploadedName, uploadedUrl);
            showPostUploadActions(uploadedName, uploadedUrl);

            if (solutionText && data.solution) {
                solutionText.textContent = data.solution;
            }
            if (solutionSection) {
                solutionSection.hidden = true;
            }
            if (openSolutionBtn) {
                openSolutionBtn.textContent = 'Решение';
                openSolutionBtn.setAttribute('aria-expanded', 'false');
            }

            if (uploadForm) {
                uploadForm.hidden = true;
            }
        }

        function requestJson(url, options) {
            return fetch(url, options).then(function (response) {
                return response.json().then(function (data) {
                    if (!response.ok) {
                        throw new Error(data.message || data.error || 'Ошибка запроса');
                    }
                    return data;
                });
            });
        }

        function loadProgress() {
            return requestJson('/task/' + taskId + '/progress').then(function (data) {
                state.solved = Boolean(data.is_solved);
                if (progressBadge) {
                    progressBadge.textContent = state.solved ? 'Решено' : 'Ожидает файл';
                    progressBadge.className = 'task-status-chip ' + (state.solved ? 'is-solved' : 'is-new');
                }
                if (state.solved) {
                    if (uploadForm) {
                        uploadForm.hidden = true;
                    }
                    if (page.dataset.uploadedFileName) {
                        showUploadedFile(page.dataset.uploadedFileName, normalizeUrlPath(page.dataset.uploadedFileUrl || ''));
                        showPostUploadActions(page.dataset.uploadedFileName, normalizeUrlPath(page.dataset.uploadedFileUrl || ''));
                    }
                    if (solutionSection) {
                        solutionSection.hidden = true;
                    }
                    if (openSolutionBtn) {
                        openSolutionBtn.textContent = 'Решение';
                        openSolutionBtn.setAttribute('aria-expanded', 'false');
                    }
                } else {
                    if (solutionSection) {
                        solutionSection.hidden = true;
                    }
                }
            }).catch(function () {
                if (progressBadge) {
                    progressBadge.textContent = 'Ошибка';
                    progressBadge.className = 'task-status-chip is-review';
                }
            });
        }

        if (fileInput) {
            fileInput.addEventListener('change', function () {
                var file = this.files && this.files[0];
                if (selectedFileName) {
                    selectedFileName.textContent = file ? file.name : 'Файл не выбран';
                }
                if (submitBtn) {
                    submitBtn.disabled = !file || state.busy;
                }
            });
        }

        function toggleSolution() {
            if (!solutionSection) {
                return;
            }

            var willShow = solutionSection.hidden;
            solutionSection.hidden = !willShow;

            if (openSolutionBtn) {
                openSolutionBtn.textContent = willShow ? 'Скрыть решение' : 'Решение';
                openSolutionBtn.setAttribute('aria-expanded', willShow ? 'true' : 'false');
            }

            if (willShow && solutionText && !solutionText.textContent.trim() && page.dataset.solutionText) {
                solutionText.textContent = page.dataset.solutionText;
            }

            if (willShow) {
                solutionSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }

        if (openSolutionBtn) {
            openSolutionBtn.setAttribute('aria-expanded', solutionSection && !solutionSection.hidden ? 'true' : 'false');
            openSolutionBtn.textContent = solutionSection && !solutionSection.hidden ? 'Скрыть решение' : 'Решение';
            openSolutionBtn.addEventListener('click', toggleSolution);
        }

        if (uploadForm) {
            uploadForm.addEventListener('submit', function (event) {
                event.preventDefault();
                if (!fileInput || !fileInput.files || !fileInput.files.length || state.busy) {
                    return;
                }

                setBusy(true);

                var formData = new FormData();
                formData.append('answer-file', fileInput.files[0]);

                requestJson('/task/' + taskId + '/submit-file', {
                    method: 'POST',
                    body: formData
                }).then(function (data) {
                    unlockSolution(data);
                }).finally(function () {
                    setBusy(false);
                });
            });
        }

        loadProgress().finally(function () {
            setBusy(false);
            if (submitBtn) {
                submitBtn.disabled = !fileInput || !fileInput.files || !fileInput.files.length || state.busy;
            }
            if (state.solved && solutionText && !solutionText.textContent.trim()) {
                solutionText.textContent = '';
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
