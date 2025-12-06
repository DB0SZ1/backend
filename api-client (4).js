/**
 * API Client - Connected to Railway Backend
 * Backend URL: https://backend-production-65be.up.railway.app
 * Enhanced with Video Upload Support
 */

const API_CONFIG = {
    // Railway backend URL
    BASE_URL: 'https://backend-n102.onrender.com/api',
    TIMEOUT: 60000, // 60 seconds for video uploads
    DEBUG: true,
    MAX_FILE_SIZE: {
        IMAGE: 5 * 1024 * 1024,  // 5MB for images
        VIDEO: 25 * 1024 * 1024  // 25MB for videos (Railway upload limit)
    }
};

const APIUtils = {
    showLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
        }
    },

    hideLoading(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            const spinner = element.querySelector('.loading-spinner');
            if (spinner) spinner.remove();
        }
    },

    showError(elementId, message) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div class="error-message show">
                    <i class="fas fa-exclamation-circle"></i> ${message}
                </div>
            `;
        }
    },

    showSuccess(elementId, message) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div class="success-message show">
                    <i class="fas fa-check-circle"></i> ${message}
                </div>
            `;
            setTimeout(() => {
                const msg = element.querySelector('.success-message');
                if (msg) msg.classList.remove('show');
            }, 5000);
        }
    },

    log(...args) {
        if (API_CONFIG.DEBUG) {
            console.log('[Celebration API]', ...args);
        }
    },

    /**
     * Validate file size before upload
     */
    validateFileSize(file, type = 'image') {
        const maxSize = type === 'video' ? API_CONFIG.MAX_FILE_SIZE.VIDEO : API_CONFIG.MAX_FILE_SIZE.IMAGE;
        if (file.size > maxSize) {
            const maxSizeMB = maxSize / (1024 * 1024);
            throw new Error(`File ${file.name} exceeds ${maxSizeMB}MB limit for ${type}s`);
        }
        return true;
    },

    /**
     * Format file size for display
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },

    /**
     * Compress image before upload (client-side)
     */
    async compressImage(file, maxWidth = 1200, quality = 0.8) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;

                    // Calculate new dimensions
                    if (width > maxWidth) {
                        height = (height * maxWidth) / width;
                        width = maxWidth;
                    }

                    canvas.width = width;
                    canvas.height = height;

                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);

                    // Convert to blob
                    canvas.toBlob(
                        (blob) => {
                            resolve(new File([blob], file.name, {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            }));
                        },
                        'image/jpeg',
                        quality
                    );
                };
                img.onerror = reject;
                img.src = e.target.result;
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
};

class CelebrationAPI {
    constructor() {
        this.baseUrl = API_CONFIG.BASE_URL;
    }

    /**
     * Generic request handler with timeout and progress tracking
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}/${endpoint}`;
        
        const config = {
            method: options.method || 'GET',
            headers: {
                'Accept': 'application/json',
                ...options.headers
            },
            mode: 'cors',
            credentials: 'omit'
        };

        // Add body for POST/PUT requests
        if (options.body) {
            if (options.body instanceof FormData) {
                // Don't set Content-Type for FormData
                config.body = options.body;
            } else {
                config.headers['Content-Type'] = 'application/json';
                config.body = JSON.stringify(options.body);
            }
        }

        APIUtils.log(`${config.method} Request:`, url);

        // Create timeout promise
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Request timeout')), API_CONFIG.TIMEOUT)
        );

        try {
            const response = await Promise.race([
                fetch(url, config),
                timeoutPromise
            ]);

            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                const text = await response.text();
                throw new Error(`Expected JSON but got ${contentType}. Response: ${text.substring(0, 200)}`);
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP ${response.status}: ${response.statusText}`);
            }

            APIUtils.log('Response:', data);
            return data;

        } catch (error) {
            APIUtils.log('Error:', error);
            
            if (error.message === 'Request timeout') {
                throw new Error('Request timed out. Please check your connection.');
            } else if (error.message.includes('Failed to fetch')) {
                throw new Error('Unable to connect to server. Please check your internet connection.');
            }
            
            throw error;
        }
    }

    /**
     * Upload with XMLHttpRequest for progress tracking
     */
    async uploadWithProgress(endpoint, formData, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const url = `${this.baseUrl}/${endpoint}`;

            // Track upload progress
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    const percentComplete = (e.loaded / e.total) * 100;
                    onProgress(percentComplete);
                }
            });

            // Handle completion
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch (e) {
                        reject(new Error('Invalid JSON response'));
                    }
                } else {
                    try {
                        const error = JSON.parse(xhr.responseText);
                        reject(new Error(error.message || `Upload failed with status ${xhr.status}`));
                    } catch (e) {
                        reject(new Error(`Upload failed with status ${xhr.status}`));
                    }
                }
            });

            // Handle errors
            xhr.addEventListener('error', () => {
                reject(new Error('Network error during upload'));
            });

            xhr.addEventListener('timeout', () => {
                reject(new Error('Upload timeout'));
            });

            // Configure and send
            xhr.open('POST', url);
            xhr.timeout = API_CONFIG.TIMEOUT;
            xhr.send(formData);
        });
    }

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        const queryParams = new URLSearchParams();
        
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                queryParams.append(key, params[key]);
            }
        });
        
        const url = queryParams.toString() ? `${endpoint}?${queryParams}` : endpoint;
        return this.request(url, { method: 'GET' });
    }

    /**
     * POST request with JSON body
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: data
        });
    }

    // ========================================
    // GALLERY API
    // ========================================
    async getGalleryFolders() {
        return this.get('gallery/folders');
    }

    async getGalleryImages(folderName) {
        return this.get('gallery/images', { folder: folderName });
    }

    // ========================================
    // MESSAGES API
    // ========================================
    async getMessages(limit = 10, offset = 0) {
        return this.get('messages', { limit, offset });
    }

    async submitMessage(data) {
        return this.post('messages', {
            name: data.name,
            relationship: data.relationship || '',
            message: data.message
        });
    }

    // ========================================
    // MEMORIES API
    // ========================================
    async getMemories(type = 'all', limit = 20, offset = 0) {
        return this.get('memories', { type, limit, offset });
    }

    async submitTextMemory(name, message) {
        return this.post('memories/text', { 
            name, 
            message 
        });
    }

    /**
     * Submit photo memories with client-side compression
     */
    async submitPhotoMemory(formData, onProgress) {
        // Get original files
        const files = formData.getAll('photos[]');
        const name = formData.get('name');
        const caption = formData.get('caption');

        // Create new FormData with compressed images
        const compressedFormData = new FormData();
        compressedFormData.append('name', name);
        compressedFormData.append('caption', caption || '');

        // Compress each image
        for (const file of files) {
            try {
                APIUtils.validateFileSize(file, 'image');
                
                // Compress image before upload
                const compressed = await APIUtils.compressImage(file);
                compressedFormData.append('photos[]', compressed, file.name);
                
                APIUtils.log(`Compressed ${file.name}: ${APIUtils.formatFileSize(file.size)} → ${APIUtils.formatFileSize(compressed.size)}`);
            } catch (error) {
                throw new Error(`Failed to process ${file.name}: ${error.message}`);
            }
        }

        // Upload with progress tracking
        if (onProgress) {
            return this.uploadWithProgress('memories/photos', compressedFormData, onProgress);
        } else {
            return this.request('memories/photos', {
                method: 'POST',
                body: compressedFormData
            });
        }
    }

    /**
     * Submit video memories with size validation
     */
    async submitVideoMemory(formData, onProgress) {
        // Validate video files
        const files = formData.getAll('videos[]');
        
        for (const file of files) {
            try {
                APIUtils.validateFileSize(file, 'video');
            } catch (error) {
                throw error;
            }
        }

        // Upload with progress tracking
        if (onProgress) {
            return this.uploadWithProgress('memories/videos', formData, onProgress);
        } else {
            return this.request('memories/videos', {
                method: 'POST',
                body: formData
            });
        }
    }

    /**
     * Submit past memory (text-based)
     */
    async submitPastMemory(data) {
        return this.post('memories/past', {
            name: data.name || 'Anonymous',
            message: data.message
        });
    }

    // ========================================
    // CANCELLATION API
    // ========================================
    async cancelReservation(data) {
        return this.post('cancel-reservation', {
            firstName: data.firstName,
            lastName: data.lastName,
            email: data.email,
            phone: data.phone || '',
            requestType: data.requestType,
            numberOfGuests: data.numberOfGuests || 0,
            reason: data.reason,
            zoomInterest: data.zoomInterest || false,
            futureUpdates: data.futureUpdates || false
        });
    }

    // ========================================
    // DONATIONS API
    // ========================================
    async createPaymentIntent(data) {
        return this.post('donations/create-intent', {
            amount: data.amount,
            donor_name: data.donor_name,
            donor_email: data.donor_email,
            charity_id: data.charity_id || '',
            charity_name: data.charity_name || '',
            message: data.message || ''
        });
    }

    async confirmDonation(paymentIntentId) {
        return this.post('donations/confirm', {
            payment_intent_id: paymentIntentId
        });
    }

    // ========================================
    // STATS API
    // ========================================
    async getStats() {
        return this.get('stats');
    }

    // ========================================
    // GOOGLE DRIVE GALLERY API
    // ========================================
    async getDriveFolders() {
        return this.get('gallery/drive/folders');
    }

    async getDriveImages(folderId) {
        return this.get('gallery/drive/images', { folderId });
    }

    async syncDriveGallery() {
        return this.post('gallery/drive/sync', {});
    }

    // ========================================
    // GOOGLE DRIVE GALLERY API
    // ========================================
    async getDriveFolders() {
        return this.get('gallery/drive/folders');
    }

    async getDriveImages(folderId) {
        return this.get('gallery/drive/images', { folderId });
    }

    async syncDriveGallery() {
        return this.post('gallery/drive/sync', {});
    }

    // ========================================
    // HEALTH CHECK
    // ========================================
    async healthCheck() {
        return this.get('health');
    }
}

// Global instance
window.celebrationAPI = new CelebrationAPI();
window.APIUtils = APIUtils;

// Initialize and test connection
document.addEventListener('DOMContentLoaded', () => {
    APIUtils.log('API Client initialized');
    APIUtils.log('Backend URL:', API_CONFIG.BASE_URL);
    
    // Test connection to Railway backend
    window.celebrationAPI.healthCheck()
        .then(data => {
            APIUtils.log('✅ Backend Connection Successful:', data);
            console.log('%c✅ Connected to Railway Backend', 'color: green; font-weight: bold; font-size: 14px;');
        })
        .catch(error => {
            console.error('❌ Backend Connection Failed:', error.message);
            console.error('Please check:');
            console.error('1. Backend is running at:', API_CONFIG.BASE_URL);
            console.error('2. CORS is enabled on Flask backend');
            console.error('3. Internet connection is stable');
        });
});