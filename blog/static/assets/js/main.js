// assets/js/main.js

document.addEventListener('DOMContentLoaded', () => {

    /* -----------------------------------------------------------
     * 1. MENU MOBILE
     * --------------------------------------------------------- */
    const btnMobile = document.getElementById('mobile-menu-toggle');
    const navMobile = document.getElementById('mobile-navigation');

    if (btnMobile && navMobile) {
        const toggleMenu = (open) => {
            const isActive = typeof open === 'boolean' ? open : !navMobile.classList.contains('active');
            btnMobile.classList.toggle('active', isActive);
            btnMobile.setAttribute('aria-expanded', isActive);
            navMobile.classList.toggle('active', isActive);
            document.body.style.overflow = isActive ? 'hidden' : '';
        };

        btnMobile.addEventListener('click', e => {
            e.stopPropagation();
            toggleMenu();
        });

        document.addEventListener('click', e => {
            if (navMobile.classList.contains('active') && !btnMobile.contains(e.target) && !navMobile.contains(e.target)) {
                toggleMenu(false);
            }
        });

        window.addEventListener('resize', () => {
            if (window.innerWidth >= 768 && navMobile.classList.contains('active')) {
                toggleMenu(false);
            }
        });
    }

    /* -----------------------------------------------------------
     * 2. SELETOR DE TEMAS (LÓGICA APRIMORADA)
     * --------------------------------------------------------- */
    const themeOptions = document.querySelectorAll('.theme-option');
    const htmlBody = document.body;
    const desktopSelectorContainer = document.querySelector('.header-theme-selector');
    
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');

    const themes = {
        serene: { color: '#a5b4fc', name: 'Serene' },
        midnight: { color: '#93c5fd', name: 'Midnight' },
        earth: { color: '#fca5a5', name: 'Earth' },
        mint: { color: '#86efac', name: 'Mint' },
        rosewater: { color: '#fda4af', name: 'Rosewater' },
        slate: { color: '#94a3b8', name: 'Slate' },
        latte: { color: '#d2b48c', name: 'Latte' },
        oceanic: { color: '#5db4d9', name: 'Oceanic' },
        amethyst: { color: '#673de6', name: 'Amethyst' },
        azure: { color: '#00b3ff', name: 'Azure' },
        forest: { color: '#006241', name: 'Forest' },
        aqua: { color: '#00b3ff', name: 'Aqua' }
    };

    const applyTheme = themeKey => {
        // Remove qualquer classe de tema anterior para evitar conflitos
        htmlBody.className = htmlBody.className.replace(/theme-\w+/g, '').trim();
        
        // Adiciona a nova classe de tema. 'serene' é o padrão (sem classe extra).
        if (themeKey !== 'serene') {
            htmlBody.classList.add(`theme-${themeKey}`);
        }

        // Salva a escolha no localStorage para persistência
        localStorage.setItem('color-theme', themeKey);

        // Atualiza a interface do seletor de tema no desktop
        const currentThemeDisplay = document.getElementById('current-theme');
        if (currentThemeDisplay && themes[themeKey]) {
            currentThemeDisplay.innerHTML =
                `<div class="current-theme-indicator" style="background:${themes[themeKey].color}"></div>
                 <span class="current-theme-text">${themes[themeKey].name}</span>`;
        }

        // Marca a opção de tema ativa (tanto no desktop quanto no mobile)
        themeOptions.forEach(opt => {
            const isActive = opt.dataset.theme === themeKey;
            opt.classList.toggle('active', isActive);
            if(opt.closest('[role="listbox"]')) {
                opt.setAttribute('aria-selected', isActive);
            }
        });
        
        // Atualiza a cor da barra de endereço do navegador em dispositivos móveis
        if (metaThemeColor && themes[themeKey]) {
            metaThemeColor.setAttribute('content', themes[themeKey].color);
        }
    };

    // Lógica para abrir e fechar o dropdown de temas no desktop
    if (desktopSelectorContainer) {
        const selectorBtn = desktopSelectorContainer.querySelector('#theme-selector-btn');
        
        selectorBtn.addEventListener('click', e => {
            e.stopPropagation();
            const isExpanded = selectorBtn.getAttribute('aria-expanded') === 'true';
            selectorBtn.setAttribute('aria-expanded', !isExpanded);
            desktopSelectorContainer.classList.toggle('active');
        });

        document.addEventListener('click', () => {
            if (desktopSelectorContainer.classList.contains('active')) {
                selectorBtn.setAttribute('aria-expanded', 'false');
                desktopSelectorContainer.classList.remove('active');
            }
        });
    }

    // Adiciona os eventos de clique e teclado para todas as opções de tema
    themeOptions.forEach(opt => {
        const themeToApply = opt.dataset.theme;
        const clickHandler = e => {
            e.stopPropagation();
            applyTheme(themeToApply);
            // Fecha o dropdown do desktop se estiver aberto
            if (desktopSelectorContainer && desktopSelectorContainer.classList.contains('active')) {
                desktopSelectorContainer.classList.remove('active');
                desktopSelectorContainer.querySelector('#theme-selector-btn').setAttribute('aria-expanded', 'false');
            }
        };

        opt.addEventListener('click', clickHandler);
        opt.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                clickHandler(e);
            }
        });
    });

    // --- INICIALIZAÇÃO DO TEMA ---
    // Pega o tema salvo, ou usa 'serene' como padrão se nada for encontrado.
    const savedTheme = localStorage.getItem('color-theme') || 'serene';
    applyTheme(savedTheme);


    /* -----------------------------------------------------------
     * 3. SEARCH: submit com Enter
     * --------------------------------------------------------- */
    document.querySelectorAll('.search-input, .mobile-search-input')
        .forEach(inp => {
            inp.addEventListener('keypress', e => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    inp.closest('form').submit();
                }
            });
        });

    /* -----------------------------------------------------------
     * 4. ANIMAÇÃO SCROLL
     * --------------------------------------------------------- */
    const fadeEls = document.querySelectorAll('.fade-in-element');
    if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        fadeEls.forEach(el => io.observe(el));
    } else {
        // Fallback para navegadores antigos: mostra todos os elementos de uma vez.
        fadeEls.forEach(el => el.classList.add('is-visible'));
    }

    /* -----------------------------------------------------------
     * 5. HEADER COM SCROLL
     * --------------------------------------------------------- */
    const scrollHeader = () => {
        const header = document.getElementById('site-header');
        if (header) {
            // Adiciona a classe .scrolled-header se a rolagem for maior que 50 pixels
            window.scrollY >= 50 ? header.classList.add('scrolled-header') 
                                 : header.classList.remove('scrolled-header');
        }
    }
    window.addEventListener('scroll', scrollHeader);

});