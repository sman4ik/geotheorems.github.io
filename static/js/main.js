const App = {
    // --- Навигация ---
    initNavbar() {
        const navbar = document.querySelector('.navbar');
        if (!navbar) return;
        window.addEventListener('scroll', () => {
            navbar.classList.toggle('scrolled', window.scrollY > 50);
        });
    },

    // --- Дропдауны ---
    activeDropdown: null,

    initDropdowns() {
        document.querySelectorAll('.nav-item.dropdown').forEach(dd => {
            const trigger = dd.querySelector('.nav-link');
            const menu = dd.querySelector('.dropdown-menu');
            if (!trigger || !menu) return;

            trigger.addEventListener('click', e => {
                e.preventDefault();
                this.toggleDropdown(dd, menu);
            });
        });

        // Закрытие по клику вне / Escape — один слушатель на document
        document.addEventListener('click', e => {
            if (this.activeDropdown && !this.activeDropdown.dd.contains(e.target)) {
                this.closeDropdown(this.activeDropdown.dd, this.activeDropdown.menu);
            }
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && this.activeDropdown) {
                this.closeDropdown(this.activeDropdown.dd, this.activeDropdown.menu);
            }
        });
    },

    toggleDropdown(dd, menu) {
        if (menu.classList.contains('active')) {
            this.closeDropdown(dd, menu);
        } else {
            this.openDropdown(dd, menu);
        }
    },

    openDropdown(dd, menu) {
        if (this.activeDropdown) this.closeDropdown(this.activeDropdown.dd, this.activeDropdown.menu);
        Object.assign(menu.style, { opacity: '1', visibility: 'visible', transform: 'translateY(0)' });
        menu.classList.add('active');
        dd.setAttribute('aria-expanded', 'true');
        this.activeDropdown = { dd, menu };
        const first = menu.querySelector('a');
        if (first) first.focus();
    },

    closeDropdown(dd, menu) {
        Object.assign(menu.style, { opacity: '0', visibility: 'hidden', transform: 'translateY(-10px)' });
        menu.classList.remove('active');
        dd.setAttribute('aria-expanded', 'false');
        this.activeDropdown = null;
    },

    // --- Модалки ---
    lastFocused: null,

    initModals() {
        // Скрыть все при загрузке
        document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');

        // Открытие
        document.querySelectorAll('[data-modal-open]').forEach(btn => {
            btn.addEventListener('click', () => this.openModal(btn.dataset.modalOpen));
        });

        // Закрытие по кнопке
        document.querySelectorAll('[data-modal-close]').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal(btn.dataset.modalClose));
        });

        // Закрытие по backdrop
        document.querySelectorAll('.modal').forEach(modal => {
            const backdrop = modal.querySelector('.modal-backdrop');
            if (backdrop) backdrop.addEventListener('click', () => this.closeModal(modal.id));
        });

        // Закрытие по Escape
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal').forEach(m => {
                    if (m.style.display === 'flex') this.closeModal(m.id);
                });
            }
        });
    },

    openModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        this.lastFocused = document.activeElement;
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        const closeBtn = modal.querySelector('[data-modal-close]');
        if (closeBtn) setTimeout(() => closeBtn.focus(), 100);
    },

    closeModal(id) {
        const modal = document.getElementById(id);
        if (!modal) return;
        modal.style.display = 'none';
        document.body.style.overflow = '';
        if (this.lastFocused) { this.lastFocused.focus(); this.lastFocused = null; }
    }
};

// Запуск
document.addEventListener('DOMContentLoaded', () => {
    App.initNavbar();
    App.initDropdowns();
    App.initModals();
});
