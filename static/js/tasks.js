(function () {
    'use strict';

    var NAMES = { thales: 'Фалеса', menelaus: 'Менелая', ceva: 'Чевы' };
    var DIFF = { easy: 'Лёгкая', medium: 'Средняя', hard: 'Сложная' };
    var allTasks = [];

    function init() {
        var form = document.getElementById('tasks-filter-form');
        var grid = document.getElementById('tasks-grid');
        var loading = document.getElementById('tasks-loading');
        if (!form || !grid) {
            console.warn('Tasks: form or grid not found');
            return;
        }

        var urlParams = new URLSearchParams(window.location.search);
        var theoremParam = urlParams.get('theorem');
        if (theoremParam) {
            var theoremSelect = document.getElementById('theorem');
            if (theoremSelect) theoremSelect.value = theoremParam;
        }

        form.querySelectorAll('.filter-select').forEach(function (select) {
            select.addEventListener('change', filterTasks);
        });

        function getParams() {
            var fd = new FormData(form);
            return {
                theorem: fd.get('theorem') || 'all',
                difficulty: fd.get('difficulty') || 'all',
                solution_type: fd.get('solution_type') || 'all',
                sort: fd.get('sort') || 'created_at'
            };
        }

        function updateUrl(params) {
            var url = new URL(window.location);
            var searchParams = new URLSearchParams();
            if (params.theorem && params.theorem !== 'all') searchParams.set('theorem', params.theorem);
            if (params.difficulty && params.difficulty !== 'all') searchParams.set('difficulty', params.difficulty);
            if (params.solution_type && params.solution_type !== 'all') searchParams.set('solution_type', params.solution_type);
            if (params.sort && params.sort !== 'created_at') searchParams.set('sort', params.sort);
            url.search = searchParams.toString();
            window.history.replaceState({}, '', url);
        }

        function updateSummary(filteredTasks) {
            var solvedTotal = allTasks.filter(function (task) { return !!task.is_solved; }).length;
            var totalTasks = allTasks.length;
            var solvedFiltered = filteredTasks.filter(function (task) { return !!task.is_solved; }).length;

           
        }

        function loadTasks() {
            if (loading) loading.style.display = 'block';
            grid.style.opacity = '0.5';

            fetch('/api/tasks')
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    allTasks = (data && data.tasks && Array.isArray(data.tasks)) ? data.tasks : [];
                    filterTasks();
                })
                .catch(function (error) {
                    console.error('Tasks load error:', error);
                    allTasks = [];
                    updateSummary([]);
                    grid.innerHTML = '<div class="text-center"><p class="text-muted">Ошибка загрузки задач</p></div>';
                })
                .finally(function () {
                    if (loading) loading.style.display = 'none';
                    grid.style.opacity = '1';
                });
        }

        function filterTasks() {
            var params = getParams();
            updateUrl(params);

            var filtered = allTasks.filter(function (task) {
                if (params.theorem !== 'all' && task.theorem_type !== params.theorem) return false;
                if (params.difficulty !== 'all' && task.difficulty !== params.difficulty) return false;
                if (params.solution_type !== 'all' && task.solution_type !== params.solution_type) return false;
                return true;
            });

            if (params.sort === 'difficulty') {
                var order = { easy: 1, medium: 2, hard: 3 };
                filtered.sort(function (a, b) {
                    return (order[a.difficulty] || 4) - (order[b.difficulty] || 4);
                });
            }

            updateSummary(filtered);
            render(filtered);
        }

        function render(tasks) {
            if (!tasks.length) {
                grid.innerHTML = '<div class="text-center" style="padding:3rem;"><h3>Задачи не найдены</h3><p class="text-muted">Попробуйте изменить параметры фильтрации</p></div>';
                return;
            }

            grid.innerHTML = '<div class="tasks-grid">' + tasks.map(function (task) {
                return card(task);
            }).join('') + '</div>';

            grid.querySelectorAll('.task-card').forEach(function (cardNode) {
                cardNode.addEventListener('click', function (event) {
                    if (event.target.closest('button, a, input, select, textarea')) return;
                    var id = cardNode.dataset.taskId;
                    if (id) {
                        window.location.href = '/task/' + id;
                    }
                });
            });
        }

        function card(task) {
            var solvedClass = task.is_solved ? 'solved' : '';
            var text = task.description || task.title || '';
            var desc = text.length > 150 ? text.substring(0, 150) + '...' : text;
 
            return '<div class="card task-card ' + solvedClass + '" data-task-id="' + task.id + '">' +
                '<div class="card-header"><div class="task-card-header">' +
                '<span class="task-difficulty difficulty-' + task.difficulty + '">' + (DIFF[task.difficulty] || task.difficulty) + '</span>' +
                '<span class="text-muted task-theorem-type">' + (NAMES[task.theorem_type] || task.theorem_type) + '</span>' +
                '<span class="task-type-badge">' + (task.solution_type === 'proof' ? 'Доказательство' : 'Решение') + '</span>' +
                '</div><h4 class="card-title card-title-task">' + task.title + '</h4></div>' +
                '<div class="card-body"><p class="task-description-preview">' + desc + '</p></div>'+'</div>';
        }

        loadTasks();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
