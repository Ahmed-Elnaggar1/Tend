// ==========================================================================
// Tend AI Dashboard — Client Logic & Reactive Feed
// ==========================================================================

let currentFilter = 'all';
let currentSearch = '';
let allIssuesCache = [];

// DOM Elements
const statTotal = document.getElementById('statTotal');
const statOpen = document.getElementById('statOpen');
const statHigh = document.getElementById('statHigh');
const statDuplicates = document.getElementById('statDuplicates');
const issuesFeed = document.getElementById('issuesFeed');
const issuesCountLabel = document.getElementById('issuesCountLabel');
const searchInput = document.getElementById('searchInput');
const refreshBtn = document.getElementById('refreshBtn');
const filterButtons = document.querySelectorAll('.filter-pill');

// 1. Fetch & Render Stats
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    statTotal.textContent = data.total ?? 0;
    statOpen.textContent = data.open_count ?? 0;
    statHigh.textContent = data.high_priority ?? 0;
    statDuplicates.textContent = data.duplicates ?? 0;
  } catch (err) {
    console.error('Failed to load stats:', err);
  }
}

// 2. Fetch & Render Issues
async function loadIssues() {
  try {
    const params = new URLSearchParams();
    if (currentFilter === 'high') params.append('priority', 'high');
    if (currentFilter === 'medium') params.append('priority', 'medium');
    if (currentFilter === 'low') params.append('priority', 'low');
    if (currentFilter === 'duplicates') params.append('is_duplicate', 'true');
    if (currentSearch) params.append('search', currentSearch);

    const res = await fetch(`/api/issues?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const issues = await res.json();
    allIssuesCache = issues;

    renderIssues(issues);
  } catch (err) {
    console.error('Failed to load issues:', err);
    issuesFeed.innerHTML = `
      <div class="empty-state">
        <p>⚠️ Failed to load issues from server.</p>
      </div>
    `;
  }
}

// 3. Render Issue Cards to DOM
function renderIssues(issues) {
  issuesCountLabel.textContent = `Showing ${issues.length} issue${issues.length === 1 ? '' : 's'}`;

  if (!issues || issues.length === 0) {
    issuesFeed.innerHTML = `
      <div class="empty-state">
        <p style="font-size: 2rem; margin-bottom: 0.5rem;">🔍</p>
        <h3 style="color: #fff; margin-bottom: 0.25rem;">No issues found</h3>
        <p>There are no issues matching the current filter or search criteria.</p>
      </div>
    `;
    return;
  }

  issuesFeed.innerHTML = issues.map(issue => {
    const isDuplicate = Boolean(issue.duplicate_of_id);
    const priorityClass = getPriorityBadgeClass(issue.priority);
    const dateFormatted = issue.created_at ? formatRelativeDate(issue.created_at) : 'recently';
    const githubUrl = `https://github.com/${issue.repo_name}/issues/${issue.issue_number}`;

    return `
      <article class="issue-card ${isDuplicate ? 'is-duplicate' : ''}" id="issue-${issue.id}">
        <!-- Top Row: Issue #, Title, and Badges -->
        <div class="issue-top-row">
          <div class="issue-title-group">
            <span class="issue-number">#${issue.issue_number}</span>
            <h2 class="issue-title">${escapeHtml(issue.title)}</h2>
          </div>
          <div class="badges-group">
            ${isDuplicate ? '<span class="badge badge-duplicate">🎯 DUPLICATE</span>' : ''}
            <span class="badge badge-state">${issue.state || 'OPEN'}</span>
            <span class="badge ${priorityClass}">${issue.priority || 'MEDIUM'}</span>
          </div>
        </div>

        <!-- Duplicate Banner Notice -->
        ${isDuplicate ? `
          <div class="duplicate-banner">
            <span>🎯</span>
            <div>
              <strong>Duplicate Intercepted:</strong> This issue was flagged by <code>pgvector</code> as a semantic match to an existing issue. Priority automatically downgraded to LOW.
            </div>
          </div>
        ` : ''}

        <!-- AI Summary Box -->
        ${issue.ai_summary ? `
          <div class="ai-summary-box">
            <strong>🤖 AI Triage:</strong> ${escapeHtml(issue.ai_summary)}
          </div>
        ` : ''}

        <!-- Collapsible Draft Reply -->
        ${issue.draft_reply ? `
          <div class="draft-reply-container">
            <button class="btn-toggle-reply" onclick="toggleDraftReply('${issue.id}')">
              <span>💬</span>
              <span>View Generated Bot Reply</span>
              <span id="arrow-${issue.id}" style="font-size: 0.7rem;">▼</span>
            </button>
            <div class="draft-reply-content" id="reply-${issue.id}">
              ${escapeHtml(issue.draft_reply)}
            </div>
          </div>
        ` : ''}

        <!-- Meta Footer: Author, Date, GitHub Link -->
        <div class="issue-meta-footer">
          <span>Opened by <strong>@${escapeHtml(issue.author)}</strong> • ${dateFormatted}</span>
          <a href="${githubUrl}" target="_blank" rel="noopener noreferrer" class="github-link">
            Open on GitHub ↗
          </a>
        </div>
      </article>
    `;
  }).join('');
}

// Helpers
function getPriorityBadgeClass(priority) {
  switch ((priority || '').toUpperCase()) {
    case 'HIGH':
      return 'badge-priority-high';
    case 'LOW':
      return 'badge-priority-low';
    case 'MEDIUM':
    default:
      return 'badge-priority-medium';
  }
}

function toggleDraftReply(id) {
  const content = document.getElementById(`reply-${id}`);
  const arrow = document.getElementById(`arrow-${id}`);
  if (!content) return;

  const isOpen = content.classList.contains('open');
  if (isOpen) {
    content.classList.remove('open');
    if (arrow) arrow.textContent = '▼';
  } else {
    content.classList.add('open');
    if (arrow) arrow.textContent = '▲';
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatRelativeDate(isoStr) {
  const date = new Date(isoStr);
  const now = new Date();
  const diffSec = Math.floor((now - date) / 1000);

  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDays = Math.floor(diffHour / 24);
  return `${diffDays}d ago`;
}

// 4. Event Listeners: Filter Pills
filterButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    filterButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    loadIssues();
  });
});

// 5. Search Bar Debounced
let searchTimeout;
searchInput.addEventListener('input', (e) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    currentSearch = e.target.value.trim();
    loadIssues();
  }, 250);
});

// 6. Refresh Button
refreshBtn.addEventListener('click', async () => {
  refreshBtn.classList.add('spinning');
  await Promise.all([loadStats(), loadIssues()]);
  setTimeout(() => refreshBtn.classList.remove('spinning'), 500);
});

// Initial Load & Auto-Poll every 12 seconds for live updates
loadStats();
loadIssues();
setInterval(() => {
  loadStats();
  loadIssues();
}, 12000);
