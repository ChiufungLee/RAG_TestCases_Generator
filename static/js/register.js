class RegisterManager {
    constructor() {
        this.baseURL = '/';
        this.initialize();
    }

    initialize() {
        this.bindEvents();
        this.setupValidation();
    }

    async parseResponse(response) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            try {
                return await response.json();
            } catch {
                return null;
            }
        }

        try {
            const text = await response.text();
            return text ? { detail: text } : null;
        } catch {
            return null;
        }
    }
    
    bindEvents() {
        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleRegister();
            });
        }
    }
    
    setupValidation() {
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirmPassword');
        
        if (confirmPassword) {
            confirmPassword.addEventListener('input', () => {
                this.validatePasswordMatch();
            });
        }
        
        if (password) {
            password.addEventListener('input', () => {
                this.validatePasswordStrength();
                this.validatePasswordMatch();
            });
        }
    }
    
    validatePasswordStrength() {
        const password = document.getElementById('password');
        if (!password) return true;
        
        if (password.value.length < 6) {
            return false;
        }
        return true;
    }
    
    validatePasswordMatch() {
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirmPassword');
        
        if (!password || !confirmPassword) return true;
        
        if (confirmPassword.value && password.value !== confirmPassword.value) {
            this.showError('两次输入的密码不一致');
            return false;
        }
        return true;
    }
    
    async handleRegister() {
        const usernameInput = document.getElementById('username');
        const passwordInput = document.getElementById('password');
        const confirmPasswordInput = document.getElementById('confirmPassword');
        // const emailInput = document.getElementById('email');
        
        if (!usernameInput || !passwordInput || !confirmPasswordInput) return;
        
        const username = usernameInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        // const email = emailInput ? emailInput.value.trim() : '';
        
        // 验证输入
        if (!username || !password || !confirmPassword) {
            this.showError('请填写所有必填字段');
            return;
        }
        
        if (password !== confirmPassword) {
            this.showError('两次输入的密码不一致');
            return;
        }
        
        if (password.length < 6) {
            this.showError('密码至少需要6位字符');
            return;
        }
        
        // 显示加载状态
        this.setLoading(true);
        
        try {
            const formData = new URLSearchParams();
            formData.append('username', username);
            formData.append('password', password);

            const response = await fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: formData.toString()
            });

            // 如果是重定向响应
            if (response.redirected) {
                this.showSuccess('注册成功，正在跳转到登录页面...');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 1500);
                return;
            }

            const data = await this.parseResponse(response);

            if (response.ok) {
                this.showSuccess('注册成功，正在跳转到登录页面...');

                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else {
                this.showError(data?.detail || '注册失败');
                this.setLoading(false);
            }
        } catch (error) {
            console.error('注册请求失败:', error);
            this.showError('注册请求失败，请检查网络连接');
            this.setLoading(false);
        }
    }
    
    setLoading(isLoading) {
        const button = document.getElementById('registerButton');
        if (button) {
            if (isLoading) {
                button.disabled = true;
                button.textContent = '注册中...';
            } else {
                button.disabled = false;
                button.textContent = '注册';
            }
        }
    }
    
    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            
            // 隐藏成功消息
            const successDiv = document.getElementById('successMessage');
            if (successDiv) successDiv.style.display = 'none';
            
            // 5秒后自动隐藏错误消息
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }
    
    showSuccess(message) {
        const successDiv = document.getElementById('successMessage');
        if (successDiv) {
            successDiv.textContent = message;
            successDiv.style.display = 'block';
            
            // 隐藏错误消息
            const errorDiv = document.getElementById('errorMessage');
            if (errorDiv) errorDiv.style.display = 'none';
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    new RegisterManager();
});