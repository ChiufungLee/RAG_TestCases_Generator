// API基础URL
const API_BASE_URL = window.location.origin;

// 获取URL中的知识库ID
const urlParams = new URLSearchParams(window.location.search);
const knowledgeBaseId = urlParams.get('kb_id');
// const knowledgeBaseId = "{{ kb_id }}";

// DOM元素
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const sidebar = document.querySelector('.sidebar');
const backBtn = document.getElementById('backBtn');
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const selectFileBtn = document.getElementById('selectFileBtn');
const uploadProgress = document.getElementById('uploadProgress');
const progressFilename = document.getElementById('progressFilename');
const progressPercent = document.getElementById('progressPercent');
const progressFill = document.getElementById('progressFill');
const uploadStatus = document.getElementById('uploadStatus');
const filesTable = document.getElementById('filesTable');
const filesTableBody = document.getElementById('filesTableBody');
const loadingState = document.getElementById('loadingState');
// const loadingFilesState = document.getElementById('loadingFilesState');
const emptyFilesState = document.getElementById('emptyFilesState');
const filesCount = document.getElementById('filesCount');

// 知识库信息元素
const kbName = document.getElementById('kbName');
const kbDescription = document.getElementById('kbDescription');
const kbIcon = document.getElementById('kbIcon');
const fileCount = document.getElementById('fileCount');
const chunkCount = document.getElementById('chunkCount');
const createdDate = document.getElementById('createdDate');

// 存储知识库信息和文件列表
let knowledgeBase = null;
let files = [];

// 消息提示函数
function showMessage(message, type = 'info') {
    const existingMessage = document.querySelector('.message-alert');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message-alert message-${type}`;
    messageDiv.innerHTML = `
        <span>${message}</span>
        <button class="message-close">&times;</button>
    `;
    
    document.body.appendChild(messageDiv);
    
    // 自动消失
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.remove();
                }
            }, 300);
        }
    }, 4000);
    
    // 点击关闭按钮
    messageDiv.querySelector('.message-close').addEventListener('click', () => {
        messageDiv.remove();
    });
}

// 加载知识库详情
async function loadKnowledgeBaseDetail() {
    if (!knowledgeBaseId) {
        showMessage('未指定知识库ID', 'error');
        window.location.href = '/knowledge';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${knowledgeBaseId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        knowledgeBase = await response.json();
        console.log('知识库详情:', knowledgeBase);
        renderKnowledgeBaseDetail();
        
    } catch (error) {
        console.error('加载知识库详情失败:', error);
        showMessage(`加载知识库详情失败: ${error.message}`, 'error');
        // setTimeout(() => {
        //     window.location.href = '/knowledge';
        // }, 2000);
    }
}

// 渲染知识库详情
function renderKnowledgeBaseDetail() {
    if (!knowledgeBase) return;
    
    // 更新页面信息
    kbName.textContent = knowledgeBase.name;
    kbDescription.textContent = knowledgeBase.description || '暂无描述';
    fileCount.textContent = knowledgeBase.file_count || 0;
    // chunkCount.textContent = knowledgeBase.chunk_count || 0;
        // 计算所有文件的 chunk_count 总和
    let totalChunks = 0;
    if (knowledgeBase.files && Array.isArray(knowledgeBase.files)) {
        knowledgeBase.files.forEach(file => {
            totalChunks += file.chunk_count || 0;
        });
    }
    chunkCount.textContent = totalChunks;
    
    // 格式化创建日期
    if (knowledgeBase.created_at) {
        const created = new Date(knowledgeBase.created_at);
        createdDate.textContent = created.toLocaleDateString('zh-CN');
    }
    
    // 设置图标颜色
    const colors = [
        '#4361ee', '#3a0ca3', '#4cc9f0', '#f72585', 
        '#7209b7', '#2a9d8f', '#f8961e', '#43aa8b'
    ];
    const randomColor = colors[Math.floor(Math.random() * colors.length)];
    kbIcon.style.background = `linear-gradient(135deg, ${randomColor}, ${randomColor}99)`;
    
    // 加载文件列表
    // loadFilesList();
    
    // 渲染文件列表
    if (knowledgeBase.files && knowledgeBase.files.length > 0) {
        renderFilesList(knowledgeBase.files);
    } else {
        showEmptyFilesState();
    }
}
// 显示空文件状态
function showEmptyFilesState() {
    loadingState.style.display = 'none';
    emptyFilesState.style.display = 'block';
    filesTable.style.display = 'none';
    filesCount.textContent = '0';
}


// 渲染文件列表
function renderFilesList(files) {
    if (!files || files.length === 0) {
        showEmptyFilesState();
        return;
    }

    loadingState.style.display = 'none';
    emptyFilesState.style.display = 'none';
    filesTable.style.display = 'table';
    filesCount.textContent = files.length;

    // 清空表格内容
    filesTableBody.innerHTML = '';

    // 按上传时间倒序排列（最新的在前面）
    const sortedFiles = [...files].sort((a, b) => {
        return new Date(b.uploaded_at) - new Date(a.uploaded_at);
    });

    // 添加文件行
    sortedFiles.forEach(file => {
    const row = document.createElement('tr');
    row.className = 'file-row';
    row.dataset.fileId = file.id;

    // 格式化文件大小
    const fileSize = formatFileSize(file.file_size || 0);

    // 格式化上传时间
    let uploadedTime = '-';
    if (file.uploaded_at) {
        const date = new Date(file.uploaded_at);
        uploadedTime = date.toLocaleString('zh-CN');
    }

    // 状态标签
    let statusClass = 'status-pending';
    let statusText = '待处理';

    if (file.status === 'processing') {
        statusClass = 'status-processing';
        statusText = '处理中';
    } else if (file.status === 'completed') {
        statusClass = 'status-completed';
        statusText = '已完成';
    } else if (file.status === 'failed') {
        statusClass = 'status-failed';
        statusText = '失败';
    }

    // 状态详细描述
    let statusDetail = '';
    if (file.status === 'completed') {
        statusDetail = ` (${file.chunk_count}个片段)`;
    } else if (file.status === 'failed') {
        statusDetail = ' - 处理失败';
    }

    row.innerHTML = `
        <td>
            <i class="fas fa-file-pdf file-icon"></i>
            ${file.filename}
        </td>
        <td>${fileSize}</td>
        <td>
            <span class="status-badge ${statusClass}" title="${file.status}">
                ${statusText}${statusDetail}
            </span>
        </td>
        <td>${uploadedTime}</td>
        <td>
            <div class="file-actions">
                ${file.status === 'completed' ? `
                <button class="action-btn preview" title="预览" onclick="previewFile('${file.id}')">
                    <i class="fas fa-eye"></i>
                </button>
                ` : ''}
                <button class="action-btn delete" title="删除" onclick="deleteFile('${file.id}', '${file.filename}')">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </div>
        </td>
    `;

    filesTableBody.appendChild(row);
    });
}


// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 上传文件
async function uploadFile(file) {
    if (!file) return;
    
    // 检查文件类型
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        showMessage('只支持PDF格式文件', 'warning');
        return;
    }
    
    // 检查文件大小（限制50MB）
    if (file.size > 50 * 1024 * 1024) {
        showMessage('文件大小不能超过50MB', 'warning');
        return;
    }
    
    // 显示上传进度
    uploadProgress.style.display = 'block';
    progressFilename.textContent = file.name;
    progressPercent.textContent = '0%';
    progressFill.style.width = '0%';
    uploadStatus.className = 'upload-status processing';
    uploadStatus.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>正在上传...</span>';
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        // 创建XMLHttpRequest以获取上传进度
        const xhr = new XMLHttpRequest();
        
        // 上传进度事件
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const percentComplete = Math.round((event.loaded / event.total) * 100);
                progressPercent.textContent = `${percentComplete}%`;
                progressFill.style.width = `${percentComplete}%`;
            }
        });
        
        // 上传完成事件
        xhr.addEventListener('load', async () => {
            if (xhr.status === 200) {
                const result = JSON.parse(xhr.responseText);
                
                if (result.success) {
                    uploadStatus.className = 'upload-status completed';
                    uploadStatus.innerHTML = '<i class="fas fa-check-circle"></i> <span>上传成功，正在后台处理...</span>';
                    
                    showMessage(`文件"${file.name}"上传成功，正在后台处理`, 'success');
                    
                    // 上传成功后，等待2秒后刷新文件列表
                    setTimeout(() => {
                        // 这里可以重新加载文件列表
                        // 由于后端可能还没有处理完文件，我们可以先更新文件计数
                        const currentCount = parseInt(fileCount.textContent);
                        fileCount.textContent = currentCount + 1;
                        
                        // 隐藏进度条
                        setTimeout(() => {
                            uploadProgress.style.display = 'none';
                        }, 2000);
                        
                    }, 2000);
                } else {
                    uploadStatus.className = 'upload-status failed';
                    uploadStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> <span>上传失败</span>';
                    showMessage(`文件上传失败: ${result.message}`, 'error');
                    
                    // 3秒后隐藏进度条
                    setTimeout(() => {
                        uploadProgress.style.display = 'none';
                    }, 3000);
                }
            } else {
                uploadStatus.className = 'upload-status failed';
                uploadStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> <span>上传失败</span>';
                
                let errorMessage = '上传失败';
                try {
                    const errorData = JSON.parse(xhr.responseText);
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch (e) {
                    // 忽略解析错误
                }
                
                showMessage(errorMessage, 'error');
                
                // 3秒后隐藏进度条
                setTimeout(() => {
                    uploadProgress.style.display = 'none';
                }, 3000);
            }
        });
        
        // 上传错误事件
        xhr.addEventListener('error', () => {
            uploadStatus.className = 'upload-status failed';
            uploadStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> <span>网络错误</span>';
            showMessage('上传失败：网络错误', 'error');
            
            // 3秒后隐藏进度条
            setTimeout(() => {
                uploadProgress.style.display = 'none';
            }, 3000);
        });
        
        // 发送请求
        xhr.open('POST', `${API_BASE_URL}/api/knowledge-bases/${knowledgeBaseId}/upload`);
        xhr.send(formData);
        
    } catch (error) {
        console.error('上传文件失败:', error);
        uploadStatus.className = 'upload-status failed';
        uploadStatus.innerHTML = '<i class="fas fa-exclamation-circle"></i> <span>上传失败</span>';
        showMessage(`上传文件失败: ${error.message}`, 'error');
        
        // 3秒后隐藏进度条
        setTimeout(() => {
            uploadProgress.style.display = 'none';
        }, 3000);
    }
}

// 删除文件
async function deleteFile(fileId) {
    if (!confirm('确定要删除这个文件吗？此操作将删除文件及其所有向量数据，无法撤销。')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/knowledge-bases/${knowledgeBaseId}/files/${fileId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `删除失败，状态码: ${response.status}`);
        }
        
        showMessage('文件删除成功', 'success');
        
        // 重新加载文件列表
        // loadFilesList();
        // 从当前文件列表中移除该文件行
        const row = document.querySelector(`tr.file-row[data-file-id="${fileId}"]`);
        if (row) {
            row.remove();
        }
        
        // 更新文件计数
        const currentCount = parseInt(fileCount.textContent);
        if (currentCount > 0) {
            fileCount.textContent = currentCount - 1;
        }
        
    } catch (error) {
        console.error('删除文件失败:', error);
        showMessage(`删除文件失败: ${error.message}`, 'error');
    }
}

// 预览文件（功能待实现）
function previewFile(fileId) {
    // showMessage('文件预览功能开发中', 'info');
    const previewUrl = `/api/files/${fileId}/preview`;
    
    // 在新标签页打开
    window.open(previewUrl, '_blank');
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
    
    // 返回按钮
    backBtn.addEventListener('click', () => {
        window.location.href = '/api/v1/func/func_main';
    });
    
    // 选择文件按钮
    selectFileBtn.addEventListener('click', () => {
        fileInput.click();
    });
    
    // 文件选择变化事件
    fileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            // 只上传第一个文件（可以扩展为支持多文件上传）
            uploadFile(files[0]);
            
            // 重置文件输入
            fileInput.value = '';
        }
    });
    
    // 拖放文件事件
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            // 只上传第一个文件
            uploadFile(files[0]);
        }
    });
    
    // 窗口大小变化时调整布局
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) {
            sidebar.classList.remove('active');
        }
    });
}

// 初始化应用
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化事件监听器
    initEventListeners();
    
    // 加载知识库详情
    if (knowledgeBaseId) {
        await loadKnowledgeBaseDetail();
    } else {
        showMessage('未指定知识库ID', 'error');
        setTimeout(() => {
            window.location.href = '/knowledge';
        }, 2000);
    }
    
    // 设置当前年份
    const yearElement = document.querySelector('.sidebar-footer p');
    if (yearElement) {
        yearElement.textContent = `© ${new Date().getFullYear()} 智能助手系统`;
    }
});