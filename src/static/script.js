document.addEventListener('DOMContentLoaded', () => {
    // Renderiza os ícones
    lucide.createIcons();

    // --- LÓGICA DO HEADER STICKY ---
    const header = document.querySelector('.main-header');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('sticky');
        } else {
            header.classList.remove('sticky');
        }
    });

    // --- LÓGICA DO MODAL DE AUTENTICAÇÃO ---
    const authModal = document.getElementById('auth-modal');
    const loginBtn = document.getElementById('login-btn');
    const closeBtn = document.getElementById('modal-close-btn');

    // Funções para abrir e fechar o modal
    const openModal = () => authModal.classList.add('visible');
    const closeModal = () => authModal.classList.remove('visible');

    // Eventos
    loginBtn.addEventListener('click', openModal);
    closeBtn.addEventListener('click', closeModal);
    authModal.addEventListener('click', (e) => {
        // Fecha o modal se clicar fora do container
        if (e.target === authModal) {
            closeModal();
        }
    });

    // --- LÓGICA DE TROCA DE ABAS (LOGIN/CADASTRO) ---
    const authTabs = document.querySelectorAll('.auth-tab');
    const loginForm = document.getElementById('login-form');
    const signupForm = document.getElementById('signup-form');

    authTabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Remove a classe ativa de todas as abas e formulários
            authTabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));

            // Adiciona a classe ativa à aba clicada
            e.target.classList.add('active');

            // Mostra o formulário correspondente
            if (e.target.dataset.form === 'login') {
                loginForm.classList.add('active');
            } else {
                signupForm.classList.add('active');
            }
        });
    });

});