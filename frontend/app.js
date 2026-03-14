// ── State ──
let allTasks = [];
let taskFilter = 'all';
let processedCount = 0;
let failedCount = 0;
let sparkData = Array(12).fill(0);
let lastProcessed = 0;
const PRIORITY_COLORS = {
    CRITICAL: '#ef4444',
    HIGH: '#f59e0b',
    MEDIUM: '#3b82f6',
    LOW: '#8892a4',
};
const STATUS_COLORS = {
    completed: '#22c55e',
    running: '#3b82f6',
    queued: '#8892a4',
    retrying: '#f59e0b',
    failed: '#ef4444',
};

// ── Navigation ──
function showPage(page, el) {
    ['overview', 'tasks', 'submit', 'dlq', 'logs'].forEach(p => {
        document.getElementById(`page-${p}`).style.display = p === page ? '' : 'none';
    });
    document.querySelectorAll('.nav-item').forEach(e => e.classList.remove('active'));
    if (el) el.classList.add('active');
    const titles = {
        overview: ['System Overview', 'live · updated every 2s'],
        tasks: ['Task Feed', 'all tasks across the system'],
        submit: ['Submit Task', 'enqueue a new job'],
        dlq: ['Dead Letter Queue', 'failed tasks awaiting action'],
        logs: ['Event Log Stream', 'real-time SSE events'],
    };
    document.getElementById('page-title').textContent = titles[page][0];
    document.getElementById('page-sub').textContent = titles[page][1];
    if (page === 'tasks') renderAllTasks();
    if (page === 'dlq') fetchDLQ();
}

// ── SSE ──
function connectSSE() {
    const es = new EventSource('/events');
    es.onmessage = (e) => {
        try {
            const { event, data } = JSON.parse(e.data);
            handleEvent(event, data);
        } catch { }
    };
    es.onerror = () => setTimeout(connectSSE, 3000);
}

function handleEvent(type, data) {
    const task = data.task;

    // Update local task list
    const idx = allTasks.findIndex(t => t.task_id === task.task_id);
    if (idx >= 0) allTasks[idx] = task;
    else allTasks.unshift(task);

    if (type === 'task_completed') {
        processedCount++;
        sparkData.push(processedCount);
        if (sparkData.length > 12) sparkData.shift();
    }
    if (type === 'task_dead') failedCount++;

    const msg = formatLogMsg(type, data);
    appendLog('mini-log', type, msg);
    appendLog('full-log', type, msg);

    refreshOverview();
    renderAllTasks();
}

function formatLogMsg(type, data) {
    const worker = data.worker_id || '—';
    const name = data.task?.name || '—';
    const map = {
        task_started: `${worker} picked up <span class="highlight">${name}</span>`,
        task_completed: `${worker} completed <span class="highlight">${name}</span>`,
        task_failed: `${worker} failed <span class="highlight">${name}</span>`,
        task_retrying: `${worker} retrying <span class="highlight">${name}</span> (attempt ${data.task?.retries})`,
        task_dead: `${worker} → DLQ: <span class="highlight">${name}</span> exhausted retries`,
    };
    return map[type] || `${type} — ${name}`;
}

function appendLog(containerId, type, msg) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const levelMap = {
        task_completed: 'OK',
        task_started: 'INFO',
        task_retrying: 'WARN',
        task_failed: 'WARN',
        task_dead: 'ERR',
    };
    const level = levelMap[type] || 'INFO';
    const now = new Date();
    const ts = [now.getHours(), now.getMinutes(), now.getSeconds()]
        .map(x => String(x).padStart(2, '0')).join(':');
    const line = document.createElement('div');
    line.className = 'log-line fade-in';
    line.innerHTML = `<span class="log-time">${ts}</span><span class="log-${level}">${level.padEnd(4, ' ')}</span><span class="log-msg">${msg}</span>`;
    container.appendChild(line);
    if (container.children.length > 200) container.removeChild(container.firstChild);
    container.scrollTop = container.scrollHeight;
}

// ── Polling ──
async function poll() {
    try {
        const [statusRes, tasksRes] = await Promise.all([
            fetch('/status'),
            fetch('/tasks'),
        ]);
        const status = await statusRes.json();
        const tasksData = await tasksRes.json();
        allTasks = tasksData.tasks || [];
        updateFromStatus(status);
        refreshOverview();
        renderAllTasks();
    } catch { }
}

function updateFromStatus(status) {
    // Queue depth
    const depths = status.queue_depth || {};
    const total = status.queue_size || 0;
    document.getElementById('m-queue').textContent = total;
    document.getElementById('m-queue-sub').textContent = `${total} pending`;
    document.getElementById('queue-total-badge').textContent = `${total} total`;

    // Workers
    const workers = status.workers || [];
    const active = status.active_workers || 0;
    document.getElementById('active-workers-badge').textContent = `${active} active`;
    renderWorkers(workers);
    renderQueueBars(depths, total);

    // DLQ
    const dlqSize = status.dlq_size || 0;
    document.getElementById('m-dlq').textContent = dlqSize;

    // TPS
    const tps = (processedCount - lastProcessed) / 2;
    lastProcessed = processedCount;
    document.getElementById('tps-badge').textContent = tps.toFixed(1) + ' t/s';
}

// ── Render helpers ──
function refreshOverview() {
    document.getElementById('m-processed').textContent = processedCount;
    const rate = processedCount + failedCount > 0
        ? Math.round(processedCount / (processedCount + failedCount) * 100) : 100;
    document.getElementById('m-rate').textContent = rate + '%';
    document.getElementById('m-rate-sub').textContent = `${failedCount} failed`;
    renderSpark();
    renderRecentTasks();
}

function renderSpark() {
    const el = document.getElementById('spark');
    el.innerHTML = '';
    const max = Math.max(...sparkData, 1);
    sparkData.forEach((v, i) => {
        const bar = document.createElement('div');
        bar.className = 'spark-bar' + (i === sparkData.length - 1 ? ' active' : '');
        bar.style.height = Math.max(3, v / max * 32) + 'px';
        el.appendChild(bar);
    });
}

function renderWorkers(workers) {
    const el = document.getElementById('workers-container');
    if (!workers.length) { el.innerHTML = '<div style="color:var(--text3);font-size:12px">No workers running</div>'; return; }
    el.innerHTML = workers.map(w => {
        const busy = w.status !== 'idle';
        const load = busy ? Math.floor(Math.random() * 40 + 50) : 0;
        const barColor = busy ? (load > 80 ? '#ef4444' : '#22c55e') : 'var(--bg4)';
        return `<div class="worker-row">
      <div class="worker-id">${w.worker_id}</div>
      <span class="badge ${busy ? 'badge-green' : 'badge-gray'}" style="font-size:9px;padding:1px 7px">${w.status}</span>
      <div class="worker-bar-wrap"><div class="worker-bar" style="width:${load}%;background:${barColor}"></div></div>
      <div class="worker-task">${w.current_task || '—'}</div>
    </div>`;
    }).join('');
}

function renderQueueBars(depths, total) {
    const el = document.getElementById('queue-bars-container');
    const priorities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
    const max = Math.max(...Object.values(depths), 1);
    el.innerHTML = priorities.map(p => {
        const count = depths[p] || 0;
        const pct = (count / max) * 100;
        return `<div class="queue-row">
      <div class="queue-label">${p}</div>
      <div class="queue-bar-wrap"><div class="queue-bar" style="width:${pct}%;background:${PRIORITY_COLORS[p]}"></div></div>
      <div class="queue-count">${count}</div>
    </div>`;
    }).join('');
}

function renderRecentTasks() {
    const el = document.getElementById('recent-tasks-body');
    const recent = allTasks.slice(0, 12);
    document.getElementById('recent-count-badge').textContent = allTasks.length + ' total';
    el.innerHTML = recent.map(t => taskRow(t, false)).join('');
}

function renderAllTasks() {
    const el = document.getElementById('all-tasks-body');
    if (!el) return;
    const filtered = taskFilter === 'all' ? allTasks : allTasks.filter(t => t.status === taskFilter);
    el.innerHTML = filtered.map(t => taskRow(t, true)).join('');
}

function taskRow(t, extended) {
    const sc = STATUS_COLORS[t.status] || '#8892a4';
    const pc = PRIORITY_COLORS[t.priority_name] || '#8892a4';
    const ai = t.ai_assigned ? '<span class="ai-tag">AI</span>' : '';
    if (extended) {
        return `<tr>
      <td><span class="task-name">${ai}${t.name}</span></td>
      <td><span style="font-family:var(--mono);font-size:10px;color:var(--text3)">${t.task_type}</span></td>
      <td><span class="badge" style="background:${pc}18;color:${pc};border:1px solid ${pc}33;font-size:9px;padding:1px 7px">${t.priority_name}</span></td>
      <td style="font-family:var(--mono);font-size:10px;color:var(--text3)">${t.worker_id || '—'}</td>
      <td><span style="color:${sc};font-size:11px">${t.status}</span></td>
      <td style="font-family:var(--mono);font-size:10px;color:var(--text3)">${t.retries}</td>
      <td>${t.ai_assigned ? '<span class="ai-tag">AI</span>' : '<span style="color:var(--text3);font-size:10px">manual</span>'}</td>
    </tr>`;
    }
    return `<tr>
    <td><span class="task-name">${ai}${t.name}</span></td>
    <td><span class="badge" style="background:${pc}18;color:${pc};border:1px solid ${pc}33;font-size:9px;padding:1px 7px">${t.priority_name}</span></td>
    <td style="font-family:var(--mono);font-size:10px;color:var(--text3)">${t.worker_id || '—'}</td>
    <td><span style="color:${sc};font-size:11px">${t.status}</span></td>
  </tr>`;
}

// ── Filters ──
function setFilter(filter, btn) {
    taskFilter = filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderAllTasks();
}

// ── Submit task ──
async function submitTask() {
    const name = document.getElementById('f-name').value.trim();
    const type = document.getElementById('f-type').value;
    const priority = document.getElementById('f-priority').value;
    const rawPayload = document.getElementById('f-payload').value.trim();
    const feedback = document.getElementById('submit-feedback');
    const btn = document.getElementById('submit-btn');

    if (!name) { feedback.innerHTML = '<div class="form-error">Task name is required</div>'; return; }

    const payload = {};
    if (type === 'payment') payload.amount = parseFloat(rawPayload) || 100;
    if (type === 'image') payload.filename = rawPayload || 'image.jpg';
    if (type === 'report') payload.report_type = rawPayload || 'monthly';
    if (type === 'digest') payload.recipients = parseInt(rawPayload) || 100;

    btn.disabled = true;
    btn.textContent = 'Submitting...';

    try {
        const res = await fetch('/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, task_type: type, payload, priority: priority || undefined }),
        });
        const data = await res.json();
        if (res.ok) {
            const p = data.task.priority_name;
            const isAI = data.task.ai_assigned;
            feedback.innerHTML = `<div class="form-success">✓ Enqueued as ${p} ${isAI ? '(AI assigned)' : '(manual)'}</div>`;
            document.getElementById('f-name').value = '';
            document.getElementById('f-payload').value = '';
        } else {
            feedback.innerHTML = `<div class="form-error">${data.error}</div>`;
        }
    } catch {
        feedback.innerHTML = '<div class="form-error">Connection error</div>';
    }

    btn.disabled = false;
    btn.textContent = 'Submit Task';
    setTimeout(() => { feedback.innerHTML = ''; }, 3000);
}

// ── DLQ ──
async function fetchDLQ() {
    try {
        const res = await fetch('/dlq');
        const data = await res.json();
        const el = document.getElementById('dlq-body');
        if (!el) return;
        if (!data.tasks.length) {
            el.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text3);padding:20px">No failed tasks</td></tr>';
            return;
        }
        const pc = PRIORITY_COLORS;
        el.innerHTML = data.tasks.map(t => `<tr>
      <td><span class="task-name">${t.name}</span></td>
      <td style="font-family:var(--mono);font-size:10px;color:var(--text3)">${t.task_type}</td>
      <td><span class="badge" style="background:${pc[t.priority_name]}18;color:${pc[t.priority_name]};border:1px solid ${pc[t.priority_name]}33;font-size:9px;padding:1px 7px">${t.priority_name}</span></td>
      <td style="font-size:10px;color:var(--red);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.error || '—'}</td>
      <td style="font-family:var(--mono);font-size:10px;color:var(--text3)">${t.retries}</td>
      <td style="display:flex;gap:6px">
        <button class="btn-success" onclick="requeueOne('${t.task_id}')">Requeue</button>
        <button class="btn-danger"  onclick="discardOne('${t.task_id}')">Discard</button>
      </td>
    </tr>`).join('');
    } catch { }
}

async function requeueOne(id) {
    await fetch(`/dlq/requeue/${id}`, { method: 'POST' });
    fetchDLQ();
}

async function discardOne(id) {
    await fetch(`/dlq/${id}`, { method: 'DELETE' });
    fetchDLQ();
}

async function requeueAll() {
    await fetch('/dlq/requeue', { method: 'POST' });
    fetchDLQ();
    poll();
}

async function discardAll() {
    await fetch('/dlq', { method: 'DELETE' });
    fetchDLQ();
    poll();
}

function clearLogs() {
    document.getElementById('full-log').innerHTML = '';
}

// ── Boot ──
poll();
connectSSE();
setInterval(poll, 2000);
appendLog('mini-log', 'task_completed', 'System online — SSE stream connected');
appendLog('full-log', 'task_completed', 'TaskFlow dashboard initialised');