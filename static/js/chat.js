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

const tipsText = `
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

// 初始化应用
document.addEventListener('DOMContentLoaded', async () => {

    // 加载知识库列表
    await loadKnowledgeBases();

    const selectElement = document.getElementById('knowledgeBaseSelect');
    appState.currentKnowledgeBaseId = selectElement.value || null;

    await loadHistory(appState.currentScenario, appState.currentKnowledgeBaseId);
    
    setupEventListeners();
    
    elements.chatInput.addEventListener('input', () => {
        elements.sendBtn.disabled = elements.chatInput.value.trim() === '' || appState.isProcessing;
    });


    
    // 监听知识库选择变化
    document.getElementById('knowledgeBaseSelect').addEventListener('change', async function() {
        const selectedKbId = this.value || null;

        appState.currentKnowledgeBaseId = selectedKbId;
        appState.currentConversation = null;
        await loadHistory(appState.currentScenario, selectedKbId);

        elements.chatMessages.innerHTML = '';
        elements.chatMessages.innerHTML = tipsText;
    });

});


const userInfo = document.getElementById('userInfo');
const dropdownContent = document.getElementById('dropdownContent');
let currentRequestController = null;
let historyMenuListenerBound = false;

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

async function logout() {
    if (!confirm('确定要退出登录吗？')) {
        return;
    }

    try {
        const response = await fetch('/logout', {
            method: 'POST',
            credentials: 'include'
        });

        if (!response.ok && !response.redirected) {
            throw new Error('退出登录失败');
        }

        window.location.href = '/login?logout=true';
    } catch (error) {
        console.error('退出登录失败:', error);
        alert('退出登录失败，请稍后再试');
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
}

async function loadKnowledgeBases() {
    try {
        const response = await fetch('/api/knowledge-bases/');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const knowledgeBases = await response.json();
        const selectElement = document.getElementById('knowledgeBaseSelect');
        const currentValue = selectElement.value;

        // 清空现有选项（保留默认选项）
        while (selectElement.options.length > 1) {
            selectElement.remove(1);
        }

        knowledgeBases.forEach(kb => {
            const option = document.createElement('option');
            option.value = kb.id;
            option.textContent = "> 知识库：" + kb.name;
            selectElement.appendChild(option);
        });

        const hasCurrentKnowledgeBase = knowledgeBases.some(kb => kb.id === currentValue);
        selectElement.value = hasCurrentKnowledgeBase ? currentValue : '';
        appState.currentKnowledgeBaseId = selectElement.value || null;

    } catch (error) {
        console.error('加载知识库失败:', error);
        // 可以选择显示一个错误提示，但不影响主要功能
    }
}

// 渲染历史记录
function renderHistory(historyData) {

    elements.historyContainer.innerHTML = '';
    
    if (!historyData || !historyData.groups || historyData.groups.length === 0) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state';
        const text = document.createElement('p');
        text.textContent = '暂无历史对话记录';
        emptyState.appendChild(text);
        elements.historyContainer.appendChild(emptyState);
        return;
    }
    
    historyData.groups.forEach(group => {
        const groupElement = document.createElement('div');
        groupElement.className = 'history-section';

        const sectionTitle = document.createElement('div');
        sectionTitle.className = 'section-title';
        sectionTitle.textContent = group.time_group;
        groupElement.appendChild(sectionTitle);
        
        group.conversations.forEach(conversation => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (appState.currentConversation === conversation.id) {
                item.classList.add('active');
            }
            item.dataset.id = conversation.id;
            const titleElement = document.createElement('div');
            titleElement.className = 'conversation-title';
            titleElement.textContent = conversation.title;

            const actionsElement = document.createElement('div');
            actionsElement.className = 'conversation-actions';

            const moreBtnElement = document.createElement('button');
            moreBtnElement.className = 'more-btn';
            moreBtnElement.textContent = '···';

            const dropdownMenuElement = document.createElement('div');
            dropdownMenuElement.className = 'dropdown-menu';

            const renameButton = document.createElement('button');
            renameButton.className = 'dropdown-item rename-btn';
            renameButton.dataset.id = conversation.id;
            renameButton.textContent = '重命名';

            const deleteButton = document.createElement('button');
            deleteButton.className = 'dropdown-item delete-btn';
            deleteButton.dataset.id = conversation.id;
            deleteButton.textContent = '删除';

            dropdownMenuElement.appendChild(renameButton);
            dropdownMenuElement.appendChild(deleteButton);
            actionsElement.appendChild(moreBtnElement);
            actionsElement.appendChild(dropdownMenuElement);
            item.appendChild(titleElement);
            item.appendChild(actionsElement);
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
            const moreBtn = moreBtnElement;
            const dropdownMenu = dropdownMenuElement;
            
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
            const renameBtn = renameButton;
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
            const deleteBtn = deleteButton;
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

    if (!historyMenuListenerBound) {
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown-menu') && !e.target.closest('.more-btn')) {
                document.querySelectorAll('.dropdown-menu').forEach(menu => {
                    menu.classList.remove('show');
                });
            }
        });
        historyMenuListenerBound = true;
    }

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
                elements.chatMessages.innerHTML = tipsText;
            }
            
            
            // elements.chatTitle.textContent = conversationData.title || "对话详情";
        } else {
            console.error('加载对话内容失败');
        }
    } catch (error) {
        console.error('加载对话内容时出错:', error);
    }    
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
    const wrapper = document.createElement('div');
    wrapper.className = `message ${isUser ? 'user-message' : 'ai-message'}`;

    const header = document.createElement('div');
    header.className = 'message-header';

    const avatar = document.createElement('div');
    avatar.className = `avatar ${isUser ? 'user-avatar-small' : 'ai-avatar'}`;
    avatar.setAttribute('aria-label', isUser ? '用户头像' : 'AI头像');
    avatar.textContent = isUser ? 'U' : 'AI';

    const senderName = document.createElement('div');
    senderName.className = 'sender-name';
    senderName.textContent = isUser ? '你' : '智能助手';

    const contentElement = document.createElement('div');
    contentElement.className = 'message-content';
    if (isUser) {
        contentElement.textContent = message.content;
    } else {
        contentElement.innerHTML = DOMPurify.sanitize(marked.parse(message.content));
    }

    const actions = document.createElement('div');
    actions.className = 'message-actions';

    header.appendChild(avatar);
    header.appendChild(senderName);
    wrapper.appendChild(header);
    wrapper.appendChild(contentElement);
    wrapper.appendChild(actions);
    messageContainer.appendChild(wrapper);

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
            elements.chatMessages.innerHTML = tipsText           
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
                
            elements.chatMessages.innerHTML = tipsText  
                
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

        const aiWrapper = document.createElement('div');
        aiWrapper.className = 'message ai-message';
        const aiHeader = document.createElement('div');
        aiHeader.className = 'message-header';
        const aiAvatar = document.createElement('div');
        aiAvatar.className = 'avatar ai-avatar';
        aiAvatar.setAttribute('aria-label', 'AI头像');
        aiAvatar.textContent = 'O';
        const aiSender = document.createElement('div');
        aiSender.className = 'sender-name';
        aiSender.textContent = '智能助手';
        const contentElement = document.createElement('div');
        contentElement.className = 'message-content';
        const actionsElement = document.createElement('div');
        actionsElement.className = 'message-actions';

        aiHeader.appendChild(aiAvatar);
        aiHeader.appendChild(aiSender);
        aiWrapper.appendChild(aiHeader);
        aiWrapper.appendChild(contentElement);
        aiWrapper.appendChild(actionsElement);
        aiMessageContainer.appendChild(aiWrapper);

        elements.chatMessages.appendChild(aiMessageContainer);
        scrollToBottom();
        
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

    const wrapper = document.createElement('div');
    wrapper.className = 'message ai-message';
    const header = document.createElement('div');
    header.className = 'message-header';
    const avatar = document.createElement('div');
    avatar.className = 'avatar ai-avatar';
    avatar.setAttribute('aria-label', 'AI头像');
    avatar.textContent = 'O';
    const sender = document.createElement('div');
    sender.className = 'sender-name';
    sender.textContent = '智能助手';
    const content = document.createElement('div');
    content.className = 'message-content';
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';

    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'typing-dot';
        typingIndicator.appendChild(dot);
    }

    header.appendChild(avatar);
    header.appendChild(sender);
    content.appendChild(typingIndicator);
    wrapper.appendChild(header);
    wrapper.appendChild(content);
    container.appendChild(wrapper);

    return container;
}
// 添加打字机效果
function typeWriterEffect(messageElement, text, callback) {
    messageElement.innerHTML = DOMPurify.sanitize(marked.parse(text));
    if (callback) {
        callback();
    }
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
    alert("AI 智能测试平台");
}