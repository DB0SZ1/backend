// Charity Updates Page - Main JavaScript
// This file contains all the functionality for the charity updates page

// Toggle mobile menu
function toggleMenu() {
    const menu = document.getElementById('navMenu');
    if (menu) {
        menu.classList.toggle('active');
    }
}

// Load messages from backend
async function loadMessages() {
    try {
        if (!window.celebrationAPI) {
            console.error('API client not loaded yet');
            return;
        }

        const response = await window.celebrationAPI.getMessages(50, 0);
        
        if (response.success && response.messages) {
            const messagesContainer = document.getElementById('messagesContainer');
            
            if (!messagesContainer) {
                console.error('Messages container not found');
                return;
            }
            
            if (response.messages.length === 0) {
                messagesContainer.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: #888;">
                        <i class="fas fa-inbox" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                        <p>No messages yet. Be the first to share your thoughts!</p>
                    </div>
                `;
            } else {
                messagesContainer.innerHTML = response.messages.map(msg => `
                    <div class="message-card">
                        <div class="author">
                            <i class="fas fa-user-circle"></i> ${msg.name}
                            ${msg.relationship ? `<span style="color: #888; font-weight: normal;"> (${msg.relationship})</span>` : ''}
                        </div>
                        <div class="message-text">"${msg.message}"</div>
                        <div class="date">
                            <i class="far fa-calendar"></i> ${new Date(msg.created_at).toLocaleDateString('en-US', {year: 'numeric', month: 'long', day: 'numeric'})}
                        </div>
                    </div>
                `).join('');
            }
            
            const messagesLoading = document.querySelector('#messages .loading');
            if (messagesLoading) messagesLoading.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

// Load memories (photos & videos) from backend
async function loadMemories() {
    try {
        if (!window.celebrationAPI) {
            console.error('API client not loaded yet');
            return;
        }

        const response = await window.celebrationAPI.getMemories('all', 50, 0);
        
        if (response.success && response.memories) {
            const mediaGallery = document.getElementById('mediaGallery');
            
            if (!mediaGallery) {
                console.error('Media gallery not found');
                return;
            }
            
            if (response.memories.length === 0) {
                mediaGallery.innerHTML = `
                    <div style="text-align: center; padding: 2rem; color: #888; grid-column: 1 / -1;">
                        <i class="fas fa-images" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                        <p>No photos or videos yet. Share your memories!</p>
                    </div>
                `;
            } else {
                mediaGallery.innerHTML = response.memories.map(memory => {
                    if (memory.type === 'photo') {
                        return `
                            <div class="gallery-item">
                                <img src="${memory.image_url}" alt="${memory.caption || 'Celebration photo'}">
                                ${memory.caption ? `<div style="position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); color: white; padding: 0.5rem;">${memory.caption}</div>` : ''}
                            </div>
                        `;
                    } else if (memory.type === 'video') {
                        return `
                            <div class="gallery-item">
                                <video src="${memory.image_url}" muted controls></video>
                                <div class="play-icon"><i class="fas fa-play"></i></div>
                                ${memory.caption ? `<div style="position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); color: white; padding: 0.5rem;">${memory.caption}</div>` : ''}
                            </div>
                        `;
                    }
                    return '';
                }).join('');
            }
            
            const mediaLoading = document.querySelector('#media .loading');
            if (mediaLoading) mediaLoading.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading memories:', error);
    }
}

// Load fundraising stats from backend
async function loadFundraisingStats() {
    try {
        if (!window.celebrationAPI) {
            console.error('API client not loaded yet');
            return;
        }

        const response = await window.celebrationAPI.getStats();
        
        if (response.success) {
            const fundraisingTab = document.querySelector('#fundraising .content-card');
            
            if (!fundraisingTab) {
                console.error('Fundraising tab not found');
                return;
            }
            
            const stats = response.stats;
            
            const statsHTML = `
                <h3>Current Statistics</h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.5rem; margin: 2rem 0;">
                    <div style="background: #f5e6d3; padding: 1.5rem; border-radius: 10px; text-align: center;">
                        <div style="font-size: 2.5rem; font-weight: 600; color: #8b4513;">
                            ${stats.donor_count || 0}
                        </div>
                        <div style="color: #666; margin-top: 0.5rem;">Total Donors</div>
                    </div>
                    <div style="background: #f5e6d3; padding: 1.5rem; border-radius: 10px; text-align: center;">
                        <div style="font-size: 2.5rem; font-weight: 600; color: #8b4513;">
                            ${stats.message_count || 0}
                        </div>
                        <div style="color: #666; margin-top: 0.5rem;">Goodwill Messages</div>
                    </div>
                    <div style="background: #f5e6d3; padding: 1.5rem; border-radius: 10px; text-align: center;">
                        <div style="font-size: 2.5rem; font-weight: 600; color: #8b4513;">
                            ${(stats.photo_count || 0) + (stats.video_count || 0)}
                        </div>
                        <div style="color: #666; margin-top: 0.5rem;">Shared Memories</div>
                    </div>
                </div>
                
                <h3>Thank You!</h3>
                <p>Every contribution makes a difference. Your generosity is helping us support meaningful causes and create lasting impact.</p>
            `;
            
            const loadingDiv = fundraisingTab.querySelector('.loading');
            if (loadingDiv) {
                loadingDiv.outerHTML = statsHTML;
            }
        }
    } catch (error) {
        console.error('Error loading fundraising stats:', error);
    }
}

// Tab switching functionality
function initializeTabs() {
    const tabs = document.querySelectorAll('.pill-tab');
    const contents = document.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Remove active class from all tabs and contents
            tabs.forEach(t => t.classList.remove('active'));
            contents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked tab
            this.classList.add('active');

            // Show corresponding content
            const tabId = this.getAttribute('data-tab');
            const targetContent = document.getElementById(tabId);
            if (targetContent) {
                targetContent.classList.add('active');
            }

            // Scroll to content on mobile
            if (window.innerWidth <= 968) {
                const mainContent = document.querySelector('.main-content');
                if (mainContent) {
                    mainContent.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'start' 
                    });
                }
            }
        });
    });
}

// Smooth scrolling for navigation
function initializeSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
                const navMenu = document.getElementById('navMenu');
                if (navMenu) {
                    navMenu.classList.remove('active');
                }
            }
        });
    });
}

// Initialize everything when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('Charity Updates page loaded');
    
    // Initialize tabs
    initializeTabs();
    
    // Initialize smooth scrolling
    initializeSmoothScrolling();
    
    // Wait for API client to initialize, then load real data
    setTimeout(async () => {
        try {
            console.log('Loading data from backend...');
            await Promise.all([
                loadMessages(),
                loadMemories(),
                loadFundraisingStats()
            ]);
            console.log('Data loading complete');
        } catch (error) {
            console.error('Error loading data:', error);
            document.querySelectorAll('.loading').forEach(loader => {
                loader.innerHTML = `
                    <div style="color: #d32f2f; text-align: center;">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>Unable to load data. Please check your connection.</p>
                    </div>
                `;
            });
        }
    }, 1500); // Increased delay to ensure API client is fully loaded
});

// Make functions globally available
window.toggleMenu = toggleMenu;
window.loadMessages = loadMessages;
window.loadMemories = loadMemories;
window.loadFundraisingStats = loadFundraisingStats;
