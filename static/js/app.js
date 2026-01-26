/**
 * PubMed Scraper - Frontend Application
 * Handles API calls, progress polling, and dynamic UI updates
 */

// State management
const state = {
    jobId: null,
    papers: [],
    currentPage: 1,
    papersPerPage: 20,
    pollInterval: null,
};

// DOM Elements
const elements = {
    form: document.getElementById('scrape-form'),
    startBtn: document.getElementById('start-btn'),
    maxPapers: document.getElementById('max_papers'),
    papersCount: document.getElementById('papers-count'),
    configSection: document.getElementById('config-section'),
    progressSection: document.getElementById('progress-section'),
    resultsSection: document.getElementById('results-section'),
    progressFill: document.getElementById('progress-fill'),
    progressCount: document.getElementById('progress-count'),
    progressMax: document.getElementById('progress-max'),
    progressMessage: document.getElementById('progress-message'),
    resultsBody: document.getElementById('results-body'),
    totalPapers: document.getElementById('total-papers'),
    downloadJson: document.getElementById('download-json'),
    downloadCsv: document.getElementById('download-csv'),
    prevPage: document.getElementById('prev-page'),
    nextPage: document.getElementById('next-page'),
    pageInfo: document.getElementById('page-info'),
};

// Initialize
document.addEventListener('DOMContentLoaded', init);

function init() {
    // Update papers count display when slider changes
    elements.maxPapers.addEventListener('input', (e) => {
        elements.papersCount.textContent = e.target.value;
    });

    // Handle form submission
    elements.form.addEventListener('submit', handleSubmit);

    // Download buttons
    elements.downloadJson.addEventListener('click', () => downloadFile('json'));
    elements.downloadCsv.addEventListener('click', () => downloadFile('csv'));

    // Pagination
    elements.prevPage.addEventListener('click', () => changePage(-1));
    elements.nextPage.addEventListener('click', () => changePage(1));
}

async function handleSubmit(e) {
    e.preventDefault();

    // Get form data
    const formData = {
        query: document.getElementById('query').value,
        source: document.getElementById('source').value,
        country: document.getElementById('country').value,
        max_papers: parseInt(elements.maxPapers.value),
    };

    // Disable button and show loading
    elements.startBtn.disabled = true;
    elements.startBtn.classList.add('loading');
    elements.startBtn.innerHTML = '<span class="btn-icon">...</span> Starting...';

    try {
        // Start scraping job
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
        });

        const data = await response.json();
        state.jobId = data.job_id;

        // Show progress section
        elements.progressSection.classList.remove('hidden');
        elements.progressMax.textContent = formData.max_papers;

        // Start polling for updates
        startPolling();

    } catch (error) {
        console.error('Error starting scrape:', error);
        alert('Failed to start scraping. Please try again.');
        resetButton();
    }
}

function startPolling() {
    // Clear any existing interval
    if (state.pollInterval) {
        clearInterval(state.pollInterval);
    }

    // Poll every 500ms
    state.pollInterval = setInterval(checkStatus, 500);
    checkStatus(); // Check immediately
}

async function checkStatus() {
    if (!state.jobId) return;

    try {
        const response = await fetch(`/api/status/${state.jobId}`);
        const data = await response.json();

        // Update progress
        const progress = (data.progress / data.max_papers) * 100;
        elements.progressFill.style.width = `${Math.min(progress, 100)}%`;
        elements.progressCount.textContent = data.progress;
        elements.progressMessage.textContent = data.message;

        // Check if completed
        if (data.status === 'completed') {
            clearInterval(state.pollInterval);
            await loadResults();
            showCompleted();
        } else if (data.status === 'error') {
            clearInterval(state.pollInterval);
            elements.progressMessage.textContent = data.message;
            elements.progressMessage.style.color = '#ef4444';
            resetButton();
        }

    } catch (error) {
        console.error('Error checking status:', error);
    }
}

async function loadResults() {
    try {
        const response = await fetch(`/api/papers/${state.jobId}`);
        const data = await response.json();

        state.papers = data.papers;
        state.currentPage = 1;

        renderTable();
        elements.totalPapers.textContent = data.total;

    } catch (error) {
        console.error('Error loading results:', error);
    }
}

function renderTable() {
    const start = (state.currentPage - 1) * state.papersPerPage;
    const end = start + state.papersPerPage;
    const pagePapers = state.papers.slice(start, end);

    elements.resultsBody.innerHTML = pagePapers.map((paper, index) => `
        <tr>
            <td>${start + index + 1}</td>
            <td class="title-cell">
                ${paper.url ?
            `<a href="${paper.url}" target="_blank" rel="noopener">${escapeHtml(paper.title)}</a>` :
            escapeHtml(paper.title)}
            </td>
            <td>${escapeHtml(paper.authors || '-')}</td>
            <td>${escapeHtml(paper.journal || '-')}</td>
            <td>${paper.year || '-'}</td>
            <td><span class="country-badge country-${paper.country}">${paper.country}</span></td>
            <td><span class="source-badge source-${paper.source}">${paper.source}</span></td>
        </tr>
    `).join('');

    // Update pagination
    const totalPages = Math.ceil(state.papers.length / state.papersPerPage);
    elements.pageInfo.textContent = `Page ${state.currentPage} of ${totalPages}`;
    elements.prevPage.disabled = state.currentPage === 1;
    elements.nextPage.disabled = state.currentPage >= totalPages;
}

function changePage(delta) {
    const totalPages = Math.ceil(state.papers.length / state.papersPerPage);
    const newPage = state.currentPage + delta;

    if (newPage >= 1 && newPage <= totalPages) {
        state.currentPage = newPage;
        renderTable();
    }
}

function showCompleted() {
    elements.progressFill.style.width = '100%';
    elements.progressMessage.textContent = 'Scraping completed!';
    elements.progressMessage.style.color = '#22c55e';

    // Show results section
    elements.resultsSection.classList.remove('hidden');

    // Reset button
    resetButton();

    // Scroll to results
    elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function resetButton() {
    elements.startBtn.disabled = false;
    elements.startBtn.classList.remove('loading');
    elements.startBtn.innerHTML = '<span class="btn-icon">></span> Start Scraping';
}

async function downloadFile(format) {
    if (!state.jobId) return;

    try {
        window.location.href = `/api/download/${state.jobId}/${format}`;
    } catch (error) {
        console.error('Error downloading file:', error);
        alert('Failed to download file. Please try again.');
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
