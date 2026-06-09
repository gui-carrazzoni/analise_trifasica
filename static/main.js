document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('analysis-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.querySelector('.btn-text');
    const btnLoader = document.getElementById('btn-loader');
    const resultsSection = document.getElementById('results-section');
    const imageGallery = document.getElementById('image-gallery');

    // File Input Styling updates
    const setupFileInput = (inputId, dropId) => {
        const input = document.getElementById(inputId);
        const dropArea = document.getElementById(dropId);
        const msg = dropArea.querySelector('.file-msg');

        input.addEventListener('change', () => {
            if (input.files.length > 0) {
                msg.textContent = input.files[0].name;
                msg.style.color = '#4f46e5';
                dropArea.style.borderColor = '#4f46e5';
            } else {
                msg.textContent = `Selecionar arquivo .${inputId.split('_')[0].toUpperCase()}`;
                msg.style.color = 'var(--text-muted)';
                dropArea.style.borderColor = 'rgba(148, 163, 184, 0.4)';
            }
        });
    };

    setupFileInput('cfg_file', 'cfg-drop');
    setupFileInput('dat_file', 'dat-drop');

    const tapMode = document.getElementById('tap_mode');
    const tapManualFields = document.getElementById('tap_manual_fields');
    if (tapMode && tapManualFields) {
        tapMode.addEventListener('change', () => {
            if (tapMode.value === 'manual') {
                tapManualFields.classList.remove('hidden');
            } else {
                tapManualFields.classList.add('hidden');
            }
        });
    }

    // Handle Form Submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // UI Loading State
        submitBtn.disabled = true;
        btnText.classList.add('hidden');
        btnLoader.classList.remove('hidden');
        resultsSection.classList.add('hidden');
        imageGallery.innerHTML = '';

        const formData = new FormData(form);

        try {
            const response = await fetch('/api/analisar', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Erro ao processar a análise');
            }

            const data = await response.json();
            
            if (data.status === 'success' && data.images) {
                renderImages(data.images);
                resultsSection.classList.remove('hidden');
                // Scroll to results
                resultsSection.scrollIntoView({ behavior: 'smooth' });
            }

        } catch (error) {
            alert(`Erro: ${error.message}`);
            console.error(error);
        } finally {
            // Restore UI State
            submitBtn.disabled = false;
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
        }
    });

    function renderImages(images) {
        images.forEach(img => {
            const card = document.createElement('div');
            card.className = 'result-card';
            
            const title = document.createElement('h3');
            title.textContent = img.name;
            
            const imageEl = document.createElement('img');
            imageEl.src = img.data;
            imageEl.alt = img.name;
            imageEl.loading = 'lazy'; // Improve performance
            
            card.appendChild(title);
            card.appendChild(imageEl);
            imageGallery.appendChild(card);
        });
    }
});
