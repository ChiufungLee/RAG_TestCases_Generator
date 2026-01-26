// API基础URL（根据实际部署情况调整）
const API_BASE_URL = window.location.origin;

// 存储知识库数据
let knowledgeData = [];
let currentKnowledgeBase = null;

// DOM元素
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const sidebar = document.querySelector('.sidebar');
const knowledgeList = document.getElementById('knowledgeList');
const emptyState = document.getElementById('emptyState');
const createLibBtn = document.getElementById('createLibBtn');
const createModal = document.getElementById('createModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const cancelBtn = document.getElementById('cancelBtn');
const createForm = document.getElementById('createForm');
const searchInput = document.getElementById('searchInput');
const mainContent = document.querySelector('.main-content');
// const libCount = document.getElementById('libCount');

// 消息提示函数
function showMessage(message, type = 'info') {
    // 移除现有的消息
    const existingMessage = document.querySelector('.message-alert');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // 创建新消息元素
    const messageDiv = document.createElement('div');
    messageDiv.className = `message-alert message-${type}`;
    messageDiv.innerHTML = `
        <span>${message}</span>
        <button class="message-close">&times;</button>
    `;
    
    // 添加到页面
    document.body.appendChild(messageDiv);
    
    // 自动消失
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.style.animation = 'slideOut 0.3s ease forwards';
            
            // 添加滑出动画
            const slideOutStyle = document.createElement('style');
            slideOutStyle.textContent = `
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(slideOutStyle);
            
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.remove();
                }
            }, 300);
        }
    }, 400);
    
    // 点击关闭按钮
    messageDiv.querySelector('.message-close').addEventListener('click', () => {
        messageDiv.remove();
    });
}

// 加载知识库列表
async function loadKnowledgeBases() {
    try {
        // 显示加载状态
        knowledgeList.innerHTML = '<div class="loading-state"><i class="fas fa-spinner fa-spin"></i><p>加载知识库...</p></div>';
        
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        knowledgeData = await response.json();
        renderKnowledgeList();
        
        // 如果没有数据，显示空状态
        if (knowledgeData.length === 0) {
            emptyState.style.display = 'block';
            knowledgeList.style.display = 'none';
        } else {
            emptyState.style.display = 'none';
            knowledgeList.style.display = 'grid';
        }
        
        // 更新计数
        // libCount.textContent = knowledgeData.length;
        
    } catch (error) {
        console.error('加载知识库失败:', error);
        showMessage(`加载知识库失败: ${error.message}`, 'error');
        
        // 显示错误状态
        knowledgeList.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <p>加载知识库失败</p>
                <button onclick="loadKnowledgeBases()" class="retry-btn">重试</button>
            </div>
        `;
        
        // 添加错误状态样式
    }
}

// 渲染知识库列表
function renderKnowledgeList(data = knowledgeData) {
    if (data.length === 0) {
        knowledgeList.style.display = 'none';
        emptyState.style.display = 'block';
        // libCount.textContent = '0';
        return;
    }
    
    knowledgeList.style.display = 'grid';
    emptyState.style.display = 'none';
    // libCount.textContent = data.length;
    
    // 定义颜色数组
    const colors = [
        '#4361ee', '#3a0ca3', '#4cc9f0', '#f72585', 
        '#7209b7', '#2a9d8f', '#f8961e', '#43aa8b'
    ];
    
    // 定义图标数组
    const icons = [
        'fas fa-database', 'fas fa-book', 'fas fa-code', 'fas fa-clipboard-list',
        'fas fa-comments', 'fas fa-network-wired', 'fas fa-graduation-cap', 'fas fa-file-alt'
    ];
    
    knowledgeList.innerHTML = data.map((item, index) => {
        const color = colors[index % colors.length];
        const icon = icons[index % icons.length];
        const createdDate = new Date(item.created_at || item.updated_at).toLocaleDateString('zh-CN');
        
        return `
            <div class="lib-card" data-id="${item.id}">
                <div class="card-header">
                    <div class="lib-icon" style="background: linear-gradient(135deg, ${color}, ${color}99);">
                        <i class="${icon}"></i>
                    </div>
                    <div>
                        <h3 class="lib-name">${item.name}</h3>
                        <p class="lib-count">${item.file_count || 0} 个文档</p>
                    </div>
                </div>
                
                <div class="card-body">
                    <p class="lib-description">${item.description || '暂无描述'}</p>
                    <div class="lib-meta">
                        <span><i class="far fa-calendar-alt"></i> 创建于 ${createdDate}</span>
                        <span><i class="far fa-clock"></i> 更新: ${new Date(item.updated_at).toLocaleDateString('zh-CN')}</span>
                    </div>
                </div>
                
                <div class="card-footer">
                    <button class="create-btn open-btn" style="padding: 8px 16px; font-size: 0.9rem;" onclick="openKnowledgeBase('${item.id}')">
                        <i class="fas fa-folder-open"></i> 打开
                    </button>
                    <div class="more-container">
                        <button class="more-btn" aria-label="更多操作">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <div class="dropdown-menu">
                            <a href="#" class="dropdown-item edit" onclick="editKnowledgeBase('${item.id}')">
                                <i class="fas fa-edit"></i> 编辑
                            </a>
                            <a href="#" class="dropdown-item delete" onclick="deleteLib('${item.id}')">
                                <i class="fas fa-trash-alt"></i> 删除
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// 打开知识库详情
function openKnowledgeBase(kbId) {
    window.location.href = `/knowledge-detail?kb_id=${kbId}`;
}

// 创建知识库
async function createKnowledgeBase(name, description) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                description: description
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `创建失败，状态码: ${response.status}`);
        }
        
        const newKnowledgeBase = await response.json();
        
        // 添加到本地数据并重新渲染
        knowledgeData.unshift(newKnowledgeBase);
        renderKnowledgeList();
        
        showMessage(`知识库 "${name}" 创建成功！`, 'success');
        return newKnowledgeBase;
        
    } catch (error) {
        console.error('创建知识库失败:', error);
        showMessage(`创建知识库失败: ${error.message}`, 'error');
        throw error;
    }
}

// 更新知识库（重命名）
async function updateKnowledgeBase(kbId, name, description) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${kbId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                description: description
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `更新失败，状态码: ${response.status}`);
        }
        
        const updatedKnowledgeBase = await response.json();
        
        // 更新本地数据
        const index = knowledgeData.findIndex(item => item.id === kbId);
        if (index !== -1) {
            knowledgeData[index] = updatedKnowledgeBase;
        }
        
        renderKnowledgeList();
        
        showMessage(`知识库已重命名为 "${name}"`, 'success');
        return updatedKnowledgeBase;
        
    } catch (error) {
        console.error('更新知识库失败:', error);
        showMessage(`更新知识库失败: ${error.message}`, 'error');
        throw error;
    }
}

// 删除知识库
async function deleteKnowledgeBase(kbId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${kbId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `删除失败，状态码: ${response.status}`);
        }
        
        // 从本地数据中删除
        const index = knowledgeData.findIndex(item => item.id === kbId);
        const deletedName = knowledgeData[index]?.name || '知识库';
        
        if (index !== -1) {
            knowledgeData.splice(index, 1);
        }
        
        renderKnowledgeList();
        
        showMessage(`知识库 "${deletedName}" 已删除`, 'success');
        return true;
        
    } catch (error) {
        console.error('删除知识库失败:', error);
        showMessage(`删除知识库失败: ${error.message}`, 'error');
        throw error;
    }
}

// 获取知识库详情
async function getKnowledgeBaseDetail(kbId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${kbId}`);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `获取详情失败，状态码: ${response.status}`);
        }
        
        const knowledgeBase = await response.json();
        return knowledgeBase;
        
    } catch (error) {
        console.error('获取知识库详情失败:', error);
        showMessage(`获取知识库详情失败: ${error.message}`, 'error');
        throw error;
    }
}

// 上传文件到知识库
async function uploadFileToKnowledgeBase(kbId, file) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${kbId}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `上传失败，状态码: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`文件 "${file.name}" 上传成功，正在后台处理`, 'success');
            
            // 重新加载知识库列表以更新文件计数
            setTimeout(() => {
                loadKnowledgeBases();
            }, 200);
        } else {
            showMessage(`文件上传失败: ${result.message}`, 'error');
        }
        
        return result;
        
    } catch (error) {
        console.error('上传文件失败:', error);
        showMessage(`上传文件失败: ${error.message}`, 'error');
        throw error;
    }
}

// 获取知识库集合信息（向量存储信息）
async function getCollectionInfo(kbId) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${kbId}/collection-info`);
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `获取集合信息失败，状态码: ${response.status}`);
        }
        
        const info = await response.json();
        return info;
        
    } catch (error) {
        console.error('获取集合信息失败:', error);
        showMessage(`获取集合信息失败: ${error.message}`, 'error');
        throw error;
    }
}

// 编辑知识库
async function editKnowledgeBase(kbId) {
    try {
        // 获取知识库详情
        const knowledgeBase = await getKnowledgeBaseDetail(kbId);
        if (!knowledgeBase) return;
        
        // 显示编辑模态框
        showEditModal(knowledgeBase);
        
    } catch (error) {
        console.error('获取知识库详情失败:', error);
        showMessage(`获取知识库详情失败: ${error.message}`, 'error');
    }
}


// 显示编辑模态框
function showEditModal(knowledgeBase) {
    // 创建编辑模态框
    const editModal = document.createElement('div');
    editModal.className = 'modal active';
    editModal.id = 'editModal';
    editModal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title">编辑知识库</h3>
                <button class="close-btn" id="closeEditModalBtn">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <form id="editForm">
                <input type="hidden" id="editKbId" value="${knowledgeBase.id}">
                <div class="form-group">
                    <label for="editLibName">知识库名称</label>
                    <input type="text" id="editLibName" value="${knowledgeBase.name}" placeholder="请输入知识库名称" required>
                </div>
                
                <div class="form-group">
                    <label for="editLibDescription">描述</label>
                    <textarea id="editLibDescription" placeholder="请描述这个知识库的主要内容和用途">${knowledgeBase.description || ''}</textarea>
                </div>
                
                <div class="modal-actions">
                    <button type="button" class="btn-secondary" id="cancelEditBtn">取消</button>
                    <button type="submit" class="btn-primary">保存更改</button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(editModal);
    
    // 添加编辑模态框样式（如果不存在）
    if (!document.querySelector('#editModalStyles')) {
        const style = document.createElement('style');
        style.id = 'editModalStyles';
        style.textContent = `
            #editModal .modal-content {
                max-width: 500px;
            }
        `;
        document.head.appendChild(style);
    }
    
    // 焦点到名称输入框
    setTimeout(() => {
        document.getElementById('editLibName').focus();
    }, 100);
    
    // 事件监听器
    const closeEditModalBtn = document.getElementById('closeEditModalBtn');
    const cancelEditBtn = document.getElementById('cancelEditBtn');
    const editForm = document.getElementById('editForm');
    
    // 关闭编辑模态框
    function closeEditModal() {
        if (editModal.parentNode) {
            editModal.remove();
        }
    }
    
    closeEditModalBtn.addEventListener('click', closeEditModal);
    cancelEditBtn.addEventListener('click', closeEditModal);
    
    // 点击模态框背景关闭
    editModal.addEventListener('click', (e) => {
        if (e.target === editModal) {
            closeEditModal();
        }
    });
    
    // 编辑表单提交
    editForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const kbId = document.getElementById('editKbId').value;
        const name = document.getElementById('editLibName').value;
        const description = document.getElementById('editLibDescription').value;
        
        if (!name.trim()) {
            showMessage('请输入知识库名称', 'warning');
            return;
        }
        
        try {
            // 显示加载状态
            const submitBtn = editForm.querySelector('.btn-primary');
            const originalText = submitBtn.textContent;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';
            submitBtn.disabled = true;
            
            // 调用更新知识库API
            const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${kbId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    name: name,
                    description: description
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `更新失败，状态码: ${response.status}`);
            }
            
            const updatedKnowledgeBase = await response.json();
            
            // 更新本地数据
            const index = knowledgeData.findIndex(item => item.id === kbId);
            if (index !== -1) {
                knowledgeData[index] = updatedKnowledgeBase;
            }
            
            renderKnowledgeList();
            closeEditModal();
            
            showMessage(`知识库 "${name}" 更新成功！`, 'success');
            
        } catch (error) {
            console.error('更新知识库失败:', error);
            showMessage(`更新知识库失败: ${error.message}`, 'error');
        } finally {
            // 恢复按钮状态
            const submitBtn = editForm.querySelector('.btn-primary');
            submitBtn.textContent = '保存更改';
            submitBtn.disabled = false;
        }
    });
}

// 删除知识库（UI交互）
async function deleteLib(kbId) {
    const lib = knowledgeData.find(item => item.id === kbId);
    if (!lib) return;
    
    if (confirm(`确定要删除知识库 "${lib.name}" 吗？此操作将删除所有关联文件和向量数据，无法撤销。`)) {
        try {
            await deleteKnowledgeBase(kbId);
        } catch (error) {
            // 错误已经在函数中处理
        }
    }
}
// 初始化事件监听器
function initEventListeners() {
    // 移动端菜单切换
    mobileMenuBtn.addEventListener('click', () => {
        sidebar.classList.toggle('active');
    });

    // 关闭移动端菜单
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && 
            !sidebar.contains(e.target) && 
            !mobileMenuBtn.contains(e.target) &&
            sidebar.classList.contains('active')) {
            sidebar.classList.remove('active');
        }
    });

    // 显示创建模态框
    createLibBtn.addEventListener('click', () => {
        createModal.classList.add('active');
        document.getElementById('libName').focus();
    });

    // 关闭创建模态框
    function closeModal() {
        createModal.classList.remove('active');
        createForm.reset();
    }

    closeModalBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);

    // 创建知识库表单提交
    createForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('libName').value;
        const description = document.getElementById('libDescription').value;
        
        if (!name.trim()) {
            showMessage('请输入知识库名称', 'warning');
            return;
        }
        
        try {
            // 显示加载状态
            const submitBtn = createForm.querySelector('.btn-primary');
            const originalText = submitBtn.textContent;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 创建中...';
            submitBtn.disabled = true;
            
            await createKnowledgeBase(name, description);
            closeModal();
            
        } catch (error) {
            // 错误已经在函数中处理
        } finally {
            // 恢复按钮状态
            const submitBtn = createForm.querySelector('.btn-primary');
            submitBtn.textContent = '创建知识库';
            submitBtn.disabled = false;
        }
    });

    // 搜索功能
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase().trim();
        
        if (!searchTerm) {
            renderKnowledgeList(knowledgeData);
            return;
        }
        
        const filteredData = knowledgeData.filter(item => 
            item.name.toLowerCase().includes(searchTerm) || 
            (item.description && item.description.toLowerCase().includes(searchTerm))
        );
        
        renderKnowledgeList(filteredData);
    });

    // 窗口大小变化时调整布局
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('active');
        }
    });
}


function showAboutModal() {
    // 创建关于模态框
    // const aboutModal = document.createElement('div');
    mainContent.innerHTML = `
    <div class="about-content">
        <div class="about-section">
            <h3>关于 AI 智能测试系统</h3>
            <p>本系统是一个基于人工智能技术的测试辅助平台，通过集成检索增强生成（RAG）技术，使得系统能够从上传的知识库文档中提取关键信息，并结合大语言模型生成高质量的测试相关内容，帮助测试人员更高效地进行测试需求分析、测试用例生成和问题排查。</p>
            <h4>主要功能</h4>
            <p>需求梳理与测试策略设计</p>
            <p>测试场景和测试点分析</p>
            <p>基于知识库的测试用例生成</p>
            <p>产品问题排查与用户手册阅读</p>
            <p></p>
            <h4>本系统主要基于Python 的 FastAPI 框架和 LangChain 构建，核心 RAG 功能包括：</h4>
                <p>* 文档读取及分块</p>
                <p>* 向量化存储</p>
                <p>* 基于语义相似度的上下文检索</p>
                <p>* 检索增强的问答生成</p>
                <p>* 多知识库检索</p>
            <p></p>
            <h4>在开发此系统时，意识到当前所做的功能仍有很大的优化空间，因此在此列个 TODO List，后续有时间会继续完善。</h4>
                <p>- 增加更多文档源的支持，如数据库、API 文档等</p>
                <p>- 优化向量化存储和检索算法，提高响应速度和准确性</p>
                <p>- 测试数据生成：基于知识库内容生成测试数据，例如根据接口文档生成符合规范的请求参数</p>
                <p>- 保存生成的测试用例，记录版本</p>
                <p>- 权限管理：区分不同用户或角色,细分知识库的访问和操作权限</p>
                <p>- AI辅助测试用例评审，检查测试用例的完整性和覆盖度</p>
                <p>- 自动将生成的测试用例同步到测试管理工具（如TestRail、Jira）</p>
                <p>- 允许用户自定义测试用例模板、生成规则</p>
                <p>- 集成更多AI模型，提升生成质量</p>
            <p></p>
            <p>本项目已上传到 <a href="https://github.com/ChiufungLee/FastAPI_Local_RAG" class="email-link"> GitHub </a>，欢迎前往查看和使用~</p>
            <p>如果您在使用的过程中有任何建议或反馈，欢迎随时联系我，邮箱 <span style="color:blue;">lzfdd@937.com</span> 。</p>
            <p></p>
        </div>
    </div>
    `;

}

// 初始化应用
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化事件监听器
    initEventListeners();
    
    // 加载知识库数据
    await loadKnowledgeBases();
    
    // 设置当前年份
    const yearElement = document.querySelector('.sidebar-footer p');
    if (yearElement) {
        yearElement.textContent = `© ${new Date().getFullYear()} AI智能测试系统`;
    }
});