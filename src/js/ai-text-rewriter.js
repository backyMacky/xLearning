
/**
 * AI Text Rewriter
 * This script provides functionality to rewrite text using AI
 */

class AITextRewriter {
    constructor(options = {}) {
      this.apiEndpoint = options.apiEndpoint || '/repository/ai/rewrite-text/';
      this.csrfToken = options.csrfToken || this.getCSRFToken();
      this.styles = options.styles || [
        { id: 'formal', name: 'Formal' },
        { id: 'casual', name: 'Casual' },
        { id: 'concise', name: 'Concise' },
        { id: 'professional', name: 'Professional' },
        { id: 'simplified', name: 'Simplified' }
      ];
      this.init();
    }
    
    /**
     * Initialize the text rewriter
     */
    init() {
      // Create modal if it doesn't exist
      if (!document.getElementById('aiRewriterModal')) {
        this.createModal();
      }
      
      // Add event listener to the document to show the rewriter when text is selected
      document.addEventListener('mouseup', this.handleTextSelection.bind(this));
      
      // Add event listener to the rewrite button
      document.addEventListener('click', (e) => {
        if (e.target.classList.contains('ai-rewrite-btn') || e.target.closest('.ai-rewrite-btn')) {
          const textArea = e.target.closest('.form-group, .mb-3').querySelector('textarea, input[type="text"]');
          if (textArea) {
            this.showRewriterForElement(textArea);
          }
        }
      });
    }
    
    /**
     * Get the CSRF token
     */
    getCSRFToken() {
      const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
      return cookieValue || '';
    }
    
    /**
     * Create the rewriter modal
     */
    createModal() {
      const modal = document.createElement('div');
      modal.id = 'aiRewriterModal';
      modal.className = 'modal fade';
      modal.tabIndex = -1;
      modal.setAttribute('aria-hidden', 'true');
      
      // Create style options
      let styleOptions = '';
      this.styles.forEach(style => {
        styleOptions += `<option value="${style.id}">${style.name}</option>`;
      });
      
      modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered modal-lg">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">AI Text Rewriter</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="mb-3">
                <label for="aiRewriterText" class="form-label">Text to rewrite</label>
                <textarea class="form-control" id="aiRewriterText" rows="3"></textarea>
              </div>
              <div class="mb-3">
                <label for="aiRewriterStyle" class="form-label">Style</label>
                <select class="form-select" id="aiRewriterStyle">
                  <option value="">Standard (Improved Clarity)</option>
                  ${styleOptions}
                </select>
              </div>
              <div id="aiRewriterLoading" class="text-center py-3" style="display: none;">
                <div class="spinner-border text-primary" role="status">
                  <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2 mb-0">Generating suggestions...</p>
              </div>
              <div id="aiRewriterResults" class="mt-3" style="display: none;">
                <h6 class="fw-bold mb-2">Suggestions</h6>
                <div id="aiRewriterSuggestions" class="list-group mb-3">
                  <!-- Suggestions will be added here -->
                </div>
              </div>
              <div id="aiRewriterError" class="alert alert-danger mt-3" style="display: none;">
                <!-- Error message will be shown here -->
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" id="aiRewriterGenerateBtn">Generate Suggestions</button>
            </div>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      // Initialize as Bootstrap modal
      this.modal = new bootstrap.Modal(document.getElementById('aiRewriterModal'));
      
      // Add event listeners
      document.getElementById('aiRewriterGenerateBtn').addEventListener('click', this.generateSuggestions.bind(this));
    }
    
    /**
     * Handle text selection to show the rewriter
     */
    handleTextSelection(e) {
      // Get selected text
      const selection = window.getSelection();
      const selectedText = selection.toString().trim();
      
      // If text is selected and it's not too short or too long
      if (selectedText && selectedText.length > 10 && selectedText.length < 500) {
        // Check if the selection is within a text input or textarea
        const activeElement = document.activeElement;
        
        if (activeElement.tagName === 'TEXTAREA' || 
            (activeElement.tagName === 'INPUT' && activeElement.type === 'text')) {
          // Show a "Rewrite" button near the selection
          this.showRewriteButton(e, activeElement);
        }
      }
    }
    
    /**
     * Show a rewrite button near the text selection
     */
    showRewriteButton(e, element) {
      // Remove any existing rewrite buttons
      const existingBtn = document.querySelector('.floating-rewrite-btn');
      if (existingBtn) {
        existingBtn.remove();
      }
      
      // Create a floating button
      const button = document.createElement('button');
      button.className = 'btn btn-sm btn-primary floating-rewrite-btn';
      button.innerHTML = '<i class="ti ti-sparkles me-1"></i> Rewrite';
      button.style.position = 'absolute';
      button.style.zIndex = '1050';
      button.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
      
      // Position near the cursor
      const rect = element.getBoundingClientRect();
      button.style.top = `${e.clientY + window.scrollY}px`;
      button.style.left = `${e.clientX + window.scrollX}px`;
      
      // Add to document
      document.body.appendChild(button);
      
      // Add click event
      button.addEventListener('click', () => {
        this.showRewriterForElement(element);
        button.remove();
      });
      
      // Remove after 3 seconds or when clicked elsewhere
      setTimeout(() => {
        if (document.body.contains(button)) {
          button.remove();
        }
      }, 3000);
      
      document.addEventListener('click', (event) => {
        if (event.target !== button && !button.contains(event.target)) {
          if (document.body.contains(button)) {
            button.remove();
          }
        }
      }, { once: true });
    }
    
    /**
     * Show the rewriter for a specific text element
     */
    showRewriterForElement(element) {
      // Get the selected text or all text in the element
      let text = '';
      
      if (window.getSelection().toString().trim()) {
        text = window.getSelection().toString().trim();
        this.selectionStart = element.selectionStart;
        this.selectionEnd = element.selectionEnd;
      } else {
        text = element.value;
        this.selectionStart = 0;
        this.selectionEnd = element.value.length;
      }
      
      // Store the target element
      this.targetElement = element;
      
      // Set the text in the modal
      document.getElementById('aiRewriterText').value = text;
      
      // Reset the modal
      document.getElementById('aiRewriterResults').style.display = 'none';
      document.getElementById('aiRewriterError').style.display = 'none';
      document.getElementById('aiRewriterLoading').style.display = 'none';
      
      // Show the modal
      this.modal.show();
    }
    
    /**
     * Generate rewrite suggestions
     */
    async generateSuggestions() {
      const text = document.getElementById('aiRewriterText').value.trim();
      const style = document.getElementById('aiRewriterStyle').value;
      
      if (!text) {
        this.showError('Please enter text to rewrite');
        return;
      }
      
      // Show loading
      document.getElementById('aiRewriterLoading').style.display = 'block';
      document.getElementById('aiRewriterResults').style.display = 'none';
      document.getElementById('aiRewriterError').style.display = 'none';
      document.getElementById('aiRewriterGenerateBtn').disabled = true;
      
      try {
        // Call the API
        const response = await fetch(this.apiEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.csrfToken
          },
          body: JSON.stringify({ text, style })
        });
        
        const data = await response.json();
        
        // Hide loading
        document.getElementById('aiRewriterLoading').style.display = 'none';
        document.getElementById('aiRewriterGenerateBtn').disabled = false;
        
        if (data.success) {
          this.displaySuggestions(data.suggestions);
        } else {
          this.showError(data.message || 'Failed to generate suggestions');
        }
      } catch (error) {
        // Hide loading
        document.getElementById('aiRewriterLoading').style.display = 'none';
        document.getElementById('aiRewriterGenerateBtn').disabled = false;
        
        this.showError('An error occurred while generating suggestions');
        console.error(error);
      }
    }
    
    /**
     * Display rewrite suggestions
     */
    displaySuggestions(suggestions) {
      const container = document.getElementById('aiRewriterSuggestions');
      container.innerHTML = '';
      
      suggestions.forEach((suggestion, index) => {
        const item = document.createElement('div');
        item.className = 'list-group-item list-group-item-action';
        
        item.innerHTML = `
          <div class="d-flex w-100 justify-content-between">
            <h6 class="mb-1">Suggestion ${index + 1}</h6>
            <button type="button" class="btn btn-sm btn-primary use-suggestion-btn">
              Use This
            </button>
          </div>
          <p class="mb-1">${suggestion}</p>
        `;
        
        container.appendChild(item);
        
        // Add event listener for using the suggestion
        item.querySelector('.use-suggestion-btn').addEventListener('click', () => {
          this.useSuggestion(suggestion);
        });
      });
      
      document.getElementById('aiRewriterResults').style.display = 'block';
    }
    
    /**
     * Use a selected suggestion
     */
    useSuggestion(suggestion) {
      if (this.targetElement) {
        // Replace the selected text with the suggestion
        const originalValue = this.targetElement.value;
        this.targetElement.value = 
          originalValue.substring(0, this.selectionStart) + 
          suggestion + 
          originalValue.substring(this.selectionEnd);
        
        // Close the modal
        this.modal.hide();
        
        // Focus the element
        this.targetElement.focus();
      }
    }
    
    /**
     * Show an error message
     */
    showError(message) {
      const errorElement = document.getElementById('aiRewriterError');
      errorElement.textContent = message;
      errorElement.style.display = 'block';
    }
  }
  
  // Initialize the rewriter when the DOM is loaded
  document.addEventListener('DOMContentLoaded', () => {
    window.aiTextRewriter = new AITextRewriter({
      csrfToken: document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
    });
  });