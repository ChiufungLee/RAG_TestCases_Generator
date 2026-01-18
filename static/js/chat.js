// 当前应用状态
const appState = {
    currentScenario: 'product_manual',  // 默认场景
    currentConversation: null,
    userId: null,
    username: null,
    isProcessing: false,
    currentKnowledgeBaseId: null  // 当前选中的知识库ID
};

// DOM 元素引用
const elements = {
    scenarioGrid: document.getElementById('scenarioGrid'),
    historyContainer: document.getElementById('historyContainer'),
    chatMessages: document.getElementById('chatMessages'),
    chatInput: document.getElementById('chatInput'),
    sendBtn: document.getElementById('sendBtn'),
    newChatBtn: document.getElementById('newChatBtn'),
    // chatTitle: document.getElementById('chatTitle')
};

// 初始化应用
document.addEventListener('DOMContentLoaded', async () => {

    // 加载知识库列表
    await loadKnowledgeBases();

    const selectElement = document.getElementById('knowledgeBaseSelect');
    let firstKbId = null;
    
    if (selectElement.options.length > 0) {
        // 选项索引0是默认选项（如"请选择知识库"），所以第一个知识库在索引1
        firstKbId = selectElement.options[0].value;
        appState.currentKnowledgeBaseId = firstKbId;
        
        // 2. 同步下拉框选中状态
        selectElement.value = firstKbId;
        
        console.log(`自动设置当前知识库: ${firstKbId}`);
    } else {
        console.log("没有可用的知识库");
        appState.currentKnowledgeBaseId = null;
    }

    await loadHistory(appState.currentScenario, appState.currentKnowledgeBaseId);
    
    setupEventListeners();
    
    elements.chatInput.addEventListener('input', () => {
        elements.sendBtn.disabled = elements.chatInput.value.trim() === '' || appState.isProcessing;
    });


    
    // 监听知识库选择变化
    document.getElementById('knowledgeBaseSelect').addEventListener('change', async function() {
        const selectedKbId = this.value;
        // 更新应用状态
        appState.currentKnowledgeBaseId = selectedKbId;
        appState.currentConversation = null;
        // 刷新历史记录
        await loadHistory(appState.currentScenario, selectedKbId);
        
        // 如果有当前对话，重新加载对话内容
        if (appState.currentConversation) {
            await loadConversation(appState.currentConversation, selectedKbId);
        } else {
            // 如果没有当前对话，清空聊天区域并显示欢迎消息
            elements.chatMessages.innerHTML = '';
            elements.chatMessages.innerHTML = `
                <div class="message-container guide-text">
                    <div class="message ai-message">
                        <div class="message-content">
                            <p>你好！欢迎使用AI智能测试平台。我可以帮你：</p>
                            <p>- 梳理需求、设计测试策略、分析测试场景和测试点；</p>
                            <p>- 根据知识库和你的需求帮你生成测试用例；</p>
                            <p>- 排查产品问题、阅读用户手册等。</p>
                            <p>你可以上传文档，创建和使用新的知识库。</p>
                            <p>请选择左侧的功能场景，输入你的问题，让我们开始吧！</p>
                        </div>
                    </div>
                </div>
            `;  
            // const scenarioWelcome = getScenarioWelcomeMessage(appState.currentScenario);
            // const welcomeMsg = {
            //     role: "assistant",
            //     content: scenarioWelcome
            // };
            // addMessageToChat(welcomeMsg);
        }
    });

});


const userInfo = document.getElementById('userInfo');
const dropdownContent = document.getElementById('dropdownContent');
let currentRequestController = null;

userInfo.addEventListener('click', function(event) {
    event.stopPropagation();
    dropdownContent.classList.toggle('show');
});


document.addEventListener('click', function() {
    dropdownContent.classList.remove('show');
});

dropdownContent.addEventListener('click', function(event) {
    event.stopPropagation();
});

function logout() {
    if (confirm('确定要退出登录吗？')) {
        window.location.href = "/logout";
    }
}

// 页面刷新前保存状态
window.addEventListener('beforeunload', () => {
    if (appState.isProcessing) {
        // 提示用户
        return "AI正在响应中，确定要离开吗？";
    }
});

// 加载历史记录
async function loadHistory(scenario, knowledgeBaseId = null) {
    elements.historyContainer.innerHTML = '<div class="loader">加载历史记录中...</div>';
    try {
        // 构建查询参数
        const params = new URLSearchParams();
        params.append('scenario', scenario);
        if (knowledgeBaseId) {
            params.append('knowledge_base_id', knowledgeBaseId);
        }
        
        const response = await fetch(`/api/history?${params.toString()}`, {
            method: 'GET',
            credentials: 'include'
        });
        
        if (response.ok) {
            const historyData = await response.json();
            renderHistory(historyData);
        } else {
            console.error('加载历史记录失败');
            elements.historyContainer.innerHTML = '<div class="empty-state">无法加载历史记录</div>';
        }
    } catch (error) {
        console.error('加载历史记录时出错:', error);
        elements.historyContainer.innerHTML = '<div class="empty-state">加载历史记录时出错</div>';
    }    
    // try {
    //     const response = await fetch(`/api/history?scenario=${encodeURIComponent(scenario)}&knowledge_base_id=${encodeURIComponent(knowledgeBaseId)}`, {
    //         method: 'GET',
    //         credentials: 'include'
    //     });
        
    //     if (response.ok) {
    //         const historyData = await response.json();
    //         console.log(historyData);
    //         renderHistory(historyData);
    //     } else {
    //         console.error('加载历史记录失败');
    //         elements.historyContainer.innerHTML = '<div class="empty-state">无法加载历史记录</div>';
    //     }
    // } catch (error) {
    //     console.error('加载历史记录时出错:', error);
    //     elements.historyContainer.innerHTML = '<div class="empty-state">加载历史记录时出错</div>';
    // }
}

async function loadKnowledgeBases() {
    try {
        const response = await fetch('/api/knowledge-bases/');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const knowledgeBases = await response.json();
        const selectElement = document.getElementById('knowledgeBaseSelect');
        
        // 清空现有选项（保留默认选项）
        while (selectElement.options.length > 1) {
            selectElement.remove(1);
        }
        
        if (knowledgeBases.length === 0) {
            // 没有知识库的情况
            console.log('没有可用的知识库');
            
            // 添加一个不可选的提示选项
            const emptyOption = document.createElement('option');
            emptyOption.value = "";
            emptyOption.textContent = "暂无知识库，请先创建";
            emptyOption.disabled = true;
            emptyOption.selected = true;
            selectElement.appendChild(emptyOption);
            
            // 清空应用状态中的知识库ID
            appState.currentKnowledgeBaseId = null;
            
            // 隐藏知识库统计信息
            const kbInfo = document.getElementById('kbInfo');
            if (kbInfo) kbInfo.style.display = 'none';
            
            return;
        }

        // 添加知识库选项
        knowledgeBases.forEach(kb => {
            const option = document.createElement('option');
            option.value = kb.id;
            option.textContent = "> 知识库：" + kb.name;
            selectElement.appendChild(option);
        });
        
    } catch (error) {
        console.error('加载知识库失败:', error);
        // 可以选择显示一个错误提示，但不影响主要功能
    }
}

// 渲染历史记录
function renderHistory(historyData) {

    elements.historyContainer.innerHTML = '';
    
    if (!historyData || !historyData.groups || historyData.groups.length === 0) {
        elements.historyContainer.innerHTML = `
            <div class="empty-state">
                <p>暂无历史对话记录</p>
            </div>
        `;
        return;
    }
    
    historyData.groups.forEach(group => {
        const groupElement = document.createElement('div');
        groupElement.className = 'history-section';
        
        groupElement.innerHTML = `
            <div class="section-title">${group.time_group}</div>
        `;
        
        group.conversations.forEach(conversation => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (appState.currentConversation === conversation.id) {
                item.classList.add('active');
            }
            item.dataset.id = conversation.id;
            item.innerHTML = `
                <div class="conversation-title">${conversation.title}</div>
                <div class="conversation-actions">
                    <button class="more-btn">···</button>
                    <div class="dropdown-menu">
                        <button class="dropdown-item rename-btn" data-id="${conversation.id}">重命名</button>
                        <button class="dropdown-item delete-btn" data-id="${conversation.id}">删除</button>
                    </div>
                </div>
            `;
        // 点击加载对话
        item.addEventListener('click', (e) => {

            if (!e.target.closest('.conversation-actions')) {
                
                document.querySelectorAll('.conversation-item').forEach(el => {
                    el.classList.remove('active');
                });

                item.classList.add('active');

                loadConversation(conversation.id);
            }
        });

            // 更多按钮点击事件
            const moreBtn = item.querySelector('.more-btn');
            const dropdownMenu = item.querySelector('.dropdown-menu');
            
            moreBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // 阻止冒泡
                
                document.querySelectorAll('.dropdown-menu').forEach(menu => {
                    if (menu !== dropdownMenu) {
                        menu.classList.remove('show');
                    }
                });
                
                dropdownMenu.classList.toggle('show');
            });

            // 重命名按钮事件
            const renameBtn = item.querySelector('.rename-btn');
            renameBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                dropdownMenu.classList.remove('show');
                
                const conversationId = e.target.dataset.id;
                const newTitle = prompt('请输入新的对话标题:', conversation.title);
                
                if (newTitle && newTitle.trim() !== '') {
                    try {
                        const response = await fetch(`/api/conversation/${conversationId}/rename`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ title: newTitle.trim() }),
                            credentials: 'include'
                        });
                        
                        if (response.ok) {
                            item.querySelector('.conversation-title').textContent = newTitle.trim();
                            
                            // if (appState.currentConversation === conversationId) {
                            //     elements.chatTitle.textContent = newTitle.trim();
                            // }
                        } else {
                            alert('重命名失败，请稍后再试');
                        }
                    } catch (error) {
                        console.error('重命名请求失败:', error);
                        alert('重命名请求失败');
                    }
                }
            });
            
            // 删除按钮事件
            const deleteBtn = item.querySelector('.delete-btn');
            deleteBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                dropdownMenu.classList.remove('show');
                
                if (confirm('确定要删除这个对话吗？此操作不可恢复。')) {
                    const conversationId = e.target.dataset.id;
                    
                    try {
                        const response = await fetch(`/api/conversation/${conversationId}`, {
                            method: 'DELETE',
                            credentials: 'include'
                        });
                        
                        if (response.ok) {
                            item.remove();
                            
                            // 如果删除的是当前对话，重置状态
                            if (appState.currentConversation === conversationId) {
                                appState.currentConversation = null;
                                elements.chatMessages.innerHTML = '';
                                // elements.chatTitle.textContent = "遇事不决怎么办";
                            }
                        } else {
                            alert('删除失败，请稍后再试');
                        }
                    } catch (error) {
                        console.error('删除请求失败:', error);
                        alert('删除请求失败');
                    }
                }
            });           
            
            groupElement.appendChild(item);
        });
        
        elements.historyContainer.appendChild(groupElement);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.dropdown-menu') && !e.target.closest('.more-btn')) {
            document.querySelectorAll('.dropdown-menu').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });

}

// 加载对话内容
async function loadConversation(conversationId, knowledgeBaseId = null) {
    appState.currentConversation = conversationId;
    try {
        // 构建查询参数
        const params = new URLSearchParams();
        if (knowledgeBaseId) {
            params.append('knowledge_base_id', knowledgeBaseId);
        }
        
        const url = `/api/conversation/${conversationId}${params.toString() ? `?${params.toString()}` : ''}`;

        const response = await fetch(url, {
            method: 'GET',
            credentials: 'include'
        });
        console.log(response);
        if (response.ok) {
            const conversationData = await response.json();

            // 检查返回的数据结构
            if (Array.isArray(conversationData.messages)) {
                // 正常情况：messages 是数组
                renderConversation(conversationData);
            } else {
                console.error("对话不存在或出错:", conversationData.messages);
                elements.chatMessages.innerHTML = '';
                // 添加场景特定的欢迎消息
                elements.chatMessages.innerHTML = `
                    <div class="message-container guide-text">
                        <div class="message ai-message">
                            <div class="message-content">
                                <p>你好！欢迎使用AI智能测试平台。我可以帮你：</p>
                                <p>- 梳理需求、设计测试策略、分析测试场景和测试点；</p>
                                <p>- 根据知识库和你的需求帮你生成测试用例；</p>
                                <p>- 排查产品问题、阅读用户手册等。</p>
                                <p>你可以上传文档，创建和使用新的知识库。</p>
                                <p>请选择左侧的功能场景，输入你的问题，让我们开始吧！</p>
                            </div>
                        </div>
                    </div>
                `;   
            }
            
            
            // elements.chatTitle.textContent = conversationData.title || "对话详情";
        } else {
            console.error('加载对话内容失败');
        }
    } catch (error) {
        console.error('加载对话内容时出错:', error);
    }    
    // try {
    //     const response = await fetch(`/api/conversation/${conversationId}`, {
    //         method: 'GET',
    //         credentials: 'include'
    //     });
        
    //     if (response.ok) {
    //         const conversationData = await response.json();
    //         renderConversation(conversationData);
            
    //         elements.chatTitle.textContent = conversationData.title || "对话详情";
    //     } else {
    //         console.error('加载对话内容失败');
    //     }
    // } catch (error) {
    //     console.error('加载对话内容时出错:', error);
    // }
}

// 渲染对话内容
function renderConversation(conversation) {

    elements.chatMessages.innerHTML = '';
    
    conversation.messages.forEach(message => {
        addMessageToChat(message);
    });
    
    // scrollToBottom();
}

// 添加消息到聊天区域
function addMessageToChat(message, isRealtime = false) {
    const messageContainer = document.createElement('div');
    messageContainer.className = 'message-container';
    
    const isUser = message.role === 'user';

    // 安全渲染Markdown内容
    const renderMarkdown = (content) => {
        // 使用DOMPurify进行安全过滤
        const clean = DOMPurify.sanitize(marked.parse(content));
        return clean;
    };

    
    const content = isUser ? message.content : renderMarkdown(message.content);

    messageContainer.innerHTML = `
        <div class="message ${isUser ? 'user-message' : 'ai-message'}">
            <div class="message-header">
                <div class="avatar ${isUser ? 'user-avatar-small' : 'ai-avatar'}" aria-label="${isUser ? '用户头像' : 'AI头像'}">
                    ${isUser ? 'U' : 'AI'}
                </div>
                <div class="sender-name">${isUser ? '你' : '智能助手'}</div>
            </div>
            <div class="message-content">${content}</div>
            <div class="message-actions"></div>
        </div>
    `;
    
    elements.chatMessages.appendChild(messageContainer);
    
    // 如果是AI消息且是测试用例场景，添加导出按钮
    if (!isUser && appState.currentScenario === 'testcase_generation') {
        // 存储原始内容以便导出
        messageContainer.dataset.raw = message.content;
        // addExportButton(messageContainer);
        setTimeout(() => {
            addExportButton(messageContainer);
        }, 100);
    }
    
    // 如果是AI的实时消息，使用打字机效果
    if (!isUser && isRealtime) {
        const contentElement = messageContainer.querySelector('.message-content');
        typeWriterEffect(contentElement, message.content, () => {
            scrollToBottom();
            // 在实时消息完成后，添加导出按钮
            if (appState.currentScenario === 'testcase_generation') {
                messageContainer.dataset.raw = message.content;
                addExportButton(messageContainer);
            }
        });
    } else {
        scrollToBottom();
    }
}

// 滚动到底部
function scrollToBottom() {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

// 设置事件监听器
function setupEventListeners() {
    // 场景切换
    document.querySelectorAll('.function-item').forEach(item => {
        item.addEventListener('click', async () => {
            if (currentRequestController) {
                currentRequestController.abort();
                currentRequestController = null;
                appState.isProcessing = false;
                elements.chatInput.disabled = false;
                elements.sendBtn.disabled = false;
            }

            // 更新活动状态
            document.querySelectorAll('.function-item').forEach(el => {
                el.classList.remove('active');
            });
            item.classList.add('active');
            
            // 更新当前场景
            // appState.currentScenario = item.dataset.scenario;
            const newScenario = item.dataset.scenario;
            appState.currentScenario = newScenario;
            
            // 加载新场景的历史记录
            // loadHistory(appState.currentScenario);
            
            // 重置当前对话
            appState.currentConversation = null;
            // elements.chatTitle.textContent = "有问题就会有答案";
            
            // 清空聊天区域
            elements.chatMessages.innerHTML = '';
            // 添加场景特定的欢迎消息
            elements.chatMessages.innerHTML = `
                <div class="message-container guide-text">
                    <div class="message ai-message">
                        <div class="message-content">
                            <p>你好！欢迎使用AI智能测试平台。我可以帮你：</p>
                            <p>- 梳理需求、设计测试策略、分析测试场景和测试点；</p>
                            <p>- 根据知识库和你的需求帮你生成测试用例；</p>
                            <p>- 排查产品问题、阅读用户手册等。</p>
                            <p>你可以上传文档，创建和使用新的知识库。</p>
                            <p>请选择左侧的功能场景，输入你的问题，让我们开始吧！</p>
                        </div>
                    </div>
                </div>
            `;            
            // 根据当前选中的知识库加载新场景的历史记录
            await loadHistory(newScenario, appState.currentKnowledgeBaseId);

        });
    });
    
    // 发送消息
    elements.sendBtn.addEventListener('click', sendMessage);
    elements.chatInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!elements.sendBtn.disabled) {
                sendMessage();
            }
        }
    });
    
    elements.newChatBtn.addEventListener('click', async () => {
        try {
            // 创建新对话
            const formData = new FormData();
            formData.append('scenario', appState.currentScenario);
            if (appState.currentKnowledgeBaseId) {
                formData.append('knowledge_base_id', appState.currentKnowledgeBaseId);
            }
            console.log(formData)
            const response = await fetch('/api/conversation/new', {
                method: 'POST',
                credentials: 'include',
                body: formData
            });
            
            if (response.ok) {
                const data = await response.json();
                appState.currentConversation = data.conversation_id;
                
            elements.chatMessages.innerHTML = `
                <div class="message-container guide-text">
                    <div class="message ai-message">
                        <div class="message-content">
                            <p>你好！欢迎使用AI智能测试平台。我可以帮你：</p>
                            <p>- 梳理需求、设计测试策略、分析测试场景和测试点；</p>
                            <p>- 根据知识库和你的需求帮你生成测试用例；</p>
                            <p>- 排查产品问题、阅读用户手册等。</p>
                            <p>你可以上传文档，创建和使用新的知识库。</p>
                            <p>请选择左侧的功能场景，输入你的问题，让我们开始吧！</p>
                        </div>
                    </div>
                </div>
            `;  
                
                // 刷新历史记录
                await loadHistory(appState.currentScenario, appState.currentKnowledgeBaseId);
                
                // 高亮显示当前新建的对话
                setTimeout(() => {
                    document.querySelectorAll('.conversation-item').forEach(el => {
                        el.classList.remove('active');
                        if (el.dataset.id === appState.currentConversation) {
                            el.classList.add('active');
                        }
                    });
                }, 300); // 等待历史记录加载完成
            } else {
                throw new Error('创建新对话失败');
            }
        } catch (error) {
            console.error('创建新对话时出错:', error);
            // 如果创建失败，保持当前对话为null，但用户输入时仍会创建新对话
            appState.currentConversation = null;
            alert('创建新对话失败，请稍后再试');
        }

    });

    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const historyOverlay = document.getElementById('historyOverlay');
    const closeHistoryBtn = document.createElement('button');

    // 打开历史记录侧边栏
    function openHistorySidebar() {
        document.querySelector('.app-container').classList.add('history-open');
    }

    // 关闭历史记录侧边栏
    function closeHistorySidebar() {
        document.querySelector('.app-container').classList.remove('history-open');
    }

    // 事件监听
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', openHistorySidebar);
    }

    if (closeHistoryBtn) {
        closeHistoryBtn.addEventListener('click', closeHistorySidebar);
    }

    if (historyOverlay) {
        historyOverlay.addEventListener('click', closeHistorySidebar);
    }

    // 点击历史项时在移动端自动关闭侧边栏
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                closeHistorySidebar();
            }
        });
    });
}

// 添加获取场景欢迎消息的辅助函数
function getScenarioWelcomeMessage(scenario) {
    const scenarioWelcome = {
        "产品手册": `我是您的产品助手，专注于容灾备份产品领域。\n\n您可以询问我有关容灾备份产品的详细功能说明与操作指南。\n\n📌 例如：如何配置备份策略？`,
        "运维助手": `我是您的智能运维助手，可以协助您处理服务器运维、故障排查和性能优化等问题。\n\n请告诉我您遇到的具体问题或需求，我将提供针对性的解决方案。\n\n📌 你可以这样问我：MySQL备份失败会是什么原因？`,
        "需求挖掘": `本场景用于需求分析与挖掘，请描述您的业务背景或功能需求，我将协助您梳理系统需求并生成清晰的需求文档。\n\n📌 你可以这样问我：如何设计一个在线支付系统的需求？`,
        "用例生成": `请输入您需要测试的功能描述，我将自动生成对应的测试用例，并支持导出 CSV 文件到 Excel 查看。\n\n📌 你可以这样问我：请根据用户登录功能生成测试用例。`
    };
    
    return scenarioWelcome[scenario] || "你好！我是你的智能助手，我可以帮助你进行需求分析、测试用例生成、问题排查、文档查询等。请选择对应的场景，来开始我们的对话吧~~";
}

// 发送消息事件
async function sendMessage() {

    // 取消之前的请求
    if (currentRequestController) {
        currentRequestController.abort();
        currentRequestController = null;
    }

    const message = elements.chatInput.value.trim();
    if (!message || appState.isProcessing) return;
    
    // 禁用输入和发送按钮
    appState.isProcessing = true;
    elements.chatInput.disabled = true;
    elements.sendBtn.disabled = true;
    
    const userMessage = {
        role: 'user',
        content: message
    };
    addMessageToChat(userMessage);
    
    elements.chatInput.value = '';
    
    // 显示AI正在输入
    const aiTypingElement = createTypingIndicator();
    elements.chatMessages.appendChild(aiTypingElement);
    scrollToBottom();
    
    try {

        // 如果当前没有对话，先创建一个新对话
        if (!appState.currentConversation) {
            try {
                const formData = new FormData();
                formData.append('scenario', appState.currentScenario);
                if (appState.currentKnowledgeBaseId) {
                    formData.append('knowledge_base_id', appState.currentKnowledgeBaseId);
                }
                
                const createResponse = await fetch('/api/conversation/new', {
                    method: 'POST',
                    credentials: 'include',
                    body: formData
                });
                
                if (createResponse.ok) {
                    const data = await createResponse.json();
                    appState.currentConversation = data.conversation_id;
                } else {
                    throw new Error('创建对话失败');
                }
            } catch (createError) {
                console.error('创建对话时出错:', createError);
                throw new Error('无法创建新对话');
            }
        }
        
        // 构建请求体，包含对话ID
        const requestBody = {
            message: message,
            scenario: appState.currentScenario,
            conversation_id: appState.currentConversation
        };
        
        const guide_text = document.querySelector('.guide-text');
        if (guide_text) {
        guide_text.classList.add("hidden");
        }

        // 创建AI消息容器（用于流式内容）
        const aiMessageContainer = document.createElement('div');
        aiMessageContainer.className = 'message-container';
        
        aiMessageContainer.innerHTML = `
            <div class="message ai-message">
                <div class="message-header">
                    <div class="avatar ai-avatar" aria-label="AI头像">O</div>
                    <div class="sender-name">智能助手</div>
                </div>
                <div class="message-content"></div>
                <div class="message-actions"></div>
            </div>
        `;
        
        elements.chatMessages.appendChild(aiMessageContainer);
        scrollToBottom();
        
        const contentElement = aiMessageContainer.querySelector('.message-content');
        
        // 移除正在输入指示器
        aiTypingElement.remove();
        
        // 添加初始光标
        let cursor = document.createElement('span');
        cursor.className = 'typing-cursor';
        cursor.textContent = '思考中...';
        contentElement.appendChild(cursor);

        currentRequestController = new AbortController();

        // 构建请求体，包含知识库ID
        // const requestBody = {
        //     message: message,
        //     scenario: appState.currentScenario,
        //     conversation_id: appState.currentConversation
        // };
        
        // 如果选择了知识库，添加到请求体中
        if (appState.currentKnowledgeBaseId) {
            requestBody.knowledge_base_id = appState.currentKnowledgeBaseId;
        }

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody),
            signal: currentRequestController.signal
        });
        
        if (!response.ok) {
            throw new Error('请求失败');
        }
        
        // 读取流式响应
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let aiResponse = "";
        let newConversationId = null;
        let conversationTitle = null;
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            // 解码并处理事件流
            const chunk = decoder.decode(value, { stream: true });
            const events = chunk.split('\n\n').filter(event => event.trim() !== '');
            
            for (const event of events) {
                if (event.startsWith('data: ')) {
                    const dataStr = event.replace('data: ', '').trim();
                    
                    // 结束标记
                    if (dataStr === '[DONE]') {
                        break;
                    }
                    
                    try {
                        const data = JSON.parse(dataStr);
                        if (data.token) {
                            // 添加token到响应
                            aiResponse += data.token;
                            
                            // 渲染Markdown
                            contentElement.innerHTML = DOMPurify.sanitize(marked.parse(aiResponse));
                            
                            scrollToBottom();
                        }
                        
                        if (data.full_response) {
                            aiResponse = data.full_response; // 更新为完整的响应
                            // 将完整的响应存储在message容器上
                            const currentMessageContainer = contentElement.closest('.message-container');
                            if (currentMessageContainer) {
                                currentMessageContainer.dataset.raw = aiResponse;
                                // 检查是否是测试用例场景并且包含表格
                                if (appState.currentScenario === 'testcase_generation' && hasMarkdownTable(aiResponse)) {
                                    addExportButton(currentMessageContainer);
                                }
                            }
                        }

                        if (data.new_conversation_id) {
                            newConversationId = data.new_conversation_id;
                        }
                        
                        if (data.conversation_title) {
                            conversationTitle = data.conversation_title;
                        }      
                        
                    } catch (e) {
                        console.error('解析JSON失败:', e);
                    }
                }
            }
        }


                // 确保添加导出按钮（如果未在流中处理）
        if (appState.currentScenario === 'testcase_generation') {
            aiMessageContainer.dataset.raw = aiResponse;
            addExportButton(aiMessageContainer);
        }

        if (newConversationId) {
            appState.currentConversation = newConversationId;
            // elements.chatTitle.textContent = conversationTitle || "新对话";
            
            // 刷新历史记录
            // await loadHistory(appState.currentScenario);
            await loadHistory(appState.currentScenario, appState.currentKnowledgeBaseId);
        }
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('请求被取消');
        } else {
            console.error('发送消息时出错:', error);
            
            // 显示错误消息
            const errorMessage = {
                role: 'assistant',
                content: '处理您的请求时出错，请稍后再试。'
            };
            addMessageToChat(errorMessage);
        }
    } finally {
        // 重新启用输入和发送按钮
        appState.isProcessing = false;
        elements.chatInput.disabled = false;
        elements.chatInput.focus();
        currentRequestController = null;
    }
}
// 创建AI正在输入的指示器
function createTypingIndicator() {
    const container = document.createElement('div');
    container.className = 'message-container';
    
    container.innerHTML = `
        <div class="message ai-message">
            <div class="message-header">
                <div class="avatar ai-avatar" aria-label="AI头像">O</div>
                <div class="sender-name">智能助手</div>
            </div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>
    `;
    
    return container;
}
// 添加打字机效果
function typeWriterEffect(messageElement, text, callback) {
    let i = 0;
    const speed = 20; // 打字速度（毫秒/字符）
    
    function type() {
                if (i < text.length) {
            // 获取下一个字符
            const char = text.charAt(i);
            
            if (isMarkdown) {

                const partialText = text.substring(0, i + 1);

                messageElement.innerHTML = DOMPurify.sanitize(marked.parse(partialText));

            } else {

                messageElement.textContent += char;
                // 添加光标
                // messageElement.appendChild(cursor);
            }
            
            i++;
            setTimeout(type, speed);
        } else {

            cursor.remove();
            if (callback) callback();
        }
    }
    
    type();
}

// 添加导出按钮的函数
function addExportButton(messageContainer) {
    // const messageHeader = messageContainer.querySelector('.message-header');
    const messageActions = messageContainer.querySelector('.message-actions');
    if (!messageActions) return;
    
    if (messageActions.querySelector('.export-btn')) return;

    // 创建导出按钮
    const exportBtn = document.createElement('button');
    exportBtn.className = 'export-btn';
    exportBtn.innerHTML = '📥 导出';
    exportBtn.title = '导出测试用例';
    exportBtn.onclick = function(e) {
        e.stopPropagation();
        exportTestCases(messageContainer);
    };
    
    // 将按钮添加到消息头部
    messageActions.appendChild(exportBtn);
}

// 导出测试用例的函数
function exportTestCases(messageContainer) {
    // 从消息容器获取原始内容
    const rawContent = messageContainer.dataset.raw;
    if (!rawContent) {
        alert('未找到测试用例内容');
        return;
    }   
    
    // 提取表格数据
    const tableData = extractTableFromMarkdown(rawContent);
    if (!tableData || tableData.length === 0) {
        alert('未找到表格数据');
        return;
    }

    // 转换为CSV
    const csvContent = convertTableToCSV(tableData);

        // 创建下载链接
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `testcases_${new Date().getTime()}.csv`;
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function hasMarkdownTable(text) {
    // 简单的Markdown表格检测
    return text.includes('|') && text.includes('-') && 
           text.split('\n').some(line => line.trim().startsWith('|'));
}

// 从Markdown文本中提取表格数据
function extractTableFromMarkdown(text) {
    const lines = text.split('\n');
    const tableData = [];
    let inTable = false;
    
    for (let line of lines) {
        line = line.trim();
        if (line.startsWith('|') && line.endsWith('|')) {
            // 移除首尾的管道符，并分割单元格
            const cells = line.split('|').slice(1, -1).map(cell => cell.trim());
            tableData.push(cells);
            inTable = true;
        } else if (inTable) {
            // 表格结束
            break;
        }
    }
    
    // 如果表格行数少于2（没有表头和数据），则返回空
    if (tableData.length < 2) {
        return [];
    }
    
    return tableData;
}

// 将表格数据转换为CSV格式的字符串
function convertTableToCSV(tableData) {
    let csvContent = '\uFEFF';
    csvContent += tableData.map(row => 
        row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    return csvContent;
}

function about() {
    alert("© 2025 快乐生活，有问题请联系 lzfdd937@163.com ~");
}