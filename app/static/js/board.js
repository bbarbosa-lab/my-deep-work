let BOARD = null;
let BOARD_ID = null;

async function initBoard(boardId) {
  BOARD_ID = boardId;
  await reloadBoard();
  document.getElementById('btn-add-list').onclick = addList;
  document.querySelectorAll('[data-close]').forEach(el => el.onclick = closeModal);
  document.getElementById('btn-add-checklist').onclick = addChecklist;
  document.getElementById('form-comment').onsubmit = submitComment;
  document.getElementById('modal-title').onblur = saveCardTitle;
  document.getElementById('modal-desc').onchange = saveCardDesc;
  document.getElementById('modal-due').onchange = saveCardDue;
}

async function reloadBoard() {
  const r = await fetch(`/api/boards/${BOARD_ID}`, { credentials: 'include' });
  if (!r.ok) { location.href = '/login'; return; }
  BOARD = await r.json();
  document.getElementById('board-title').textContent = BOARD.name;
  document.body.style.background = BOARD.background || '#0079bf';
  renderLists();
}

function renderLists() {
  const canvas = document.getElementById('board-canvas');
  canvas.innerHTML = '';
  BOARD.lists.sort((a, b) => a.position - b.position).forEach(list => {
    const col = document.createElement('div');
    col.className = 'list-col';
    col.dataset.listId = list.id;
    col.innerHTML = `
      <div class="list-header">${esc(list.name)}</div>
      <div class="list-cards" data-list-id="${list.id}"></div>
      <div class="list-footer"><button data-add-card="${list.id}">+ Adicionar card</button></div>
    `;
    const cardsEl = col.querySelector('.list-cards');
    list.cards.sort((a, b) => a.position - b.position).forEach(card => {
      cardsEl.appendChild(renderCard(card));
    });
    canvas.appendChild(col);

    new Sortable(cardsEl, {
      group: 'cards',
      animation: 150,
      ghostClass: 'sortable-ghost',
      onEnd: async (evt) => {
        const cardId = parseInt(evt.item.dataset.cardId);
        const newListId = parseInt(evt.to.dataset.listId);
        const siblings = [...evt.to.children];
        const idx = siblings.indexOf(evt.item);
        const prev = siblings[idx - 1];
        const next = siblings[idx + 1];
        let pos = 1000;
        if (prev && next) pos = (parseFloat(prev.dataset.pos) + parseFloat(next.dataset.pos)) / 2;
        else if (prev) pos = parseFloat(prev.dataset.pos) + 1000;
        else if (next) pos = parseFloat(next.dataset.pos) / 2;
        evt.item.dataset.pos = pos;
        await fetch(`/api/cards/${cardId}/move`, {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ list_id: newListId, position: pos })
        });
      }
    });
  });

  canvas.querySelectorAll('[data-add-card]').forEach(btn => {
    btn.onclick = () => addCard(parseInt(btn.dataset.addCard));
  });
}

function renderCard(card) {
  const el = document.createElement('div');
  el.className = 'card-item';
  el.dataset.cardId = card.id;
  el.dataset.pos = card.position;
  const labels = (card.labels || []).map(l => `<span class="card-label" style="background:${l.color}"></span>`).join('');
  const meta = [];
  if (card.due_date) meta.push('📅 ' + card.due_date.slice(0, 10));
  if (card.checklist_progress && card.checklist_progress.total) {
    meta.push(`☑ ${card.checklist_progress.done}/${card.checklist_progress.total}`);
  }
  if (card.comment_count) meta.push(`💬 ${card.comment_count}`);
  el.innerHTML = `
    <div class="card-labels">${labels}</div>
    <div>${esc(card.title)}</div>
    ${meta.length ? `<div class="card-meta">${meta.join(' · ')}</div>` : ''}
  `;
  el.onclick = () => openCard(card.id);
  return el;
}

async function addList() {
  const name = prompt('Nome da lista:');
  if (!name) return;
  await fetch(`/api/boards/${BOARD_ID}/lists`, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  await reloadBoard();
}

async function addCard(listId) {
  const title = prompt('Título do card:');
  if (!title) return;
  await fetch('/api/cards', {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, list_id: listId })
  });
  await reloadBoard();
}

async function openCard(cardId) {
  const r = await fetch(`/api/cards/${cardId}`, { credentials: 'include' });
  if (!r.ok) return;
  const card = await r.json();
  document.getElementById('modal-card-id').value = card.id;
  document.getElementById('modal-title').textContent = card.title;
  document.getElementById('modal-desc').value = card.description || '';
  document.getElementById('modal-due').value = card.due_date ? card.due_date.slice(0, 16) : '';

  const labEl = document.getElementById('modal-labels');
  labEl.innerHTML = BOARD.labels.map(l => {
    const active = card.labels.some(cl => cl.id === l.id);
    return `<span class="label-chip ${active ? 'active' : ''}" style="background:${l.color}" data-label="${l.id}">${esc(l.name || ' ')}</span>`;
  }).join('');
  labEl.querySelectorAll('.label-chip').forEach(chip => {
    chip.onclick = async () => {
      await fetch(`/api/cards/${card.id}/labels`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label_id: parseInt(chip.dataset.label) })
      });
      openCard(card.id);
      reloadBoard();
    };
  });

  const clEl = document.getElementById('modal-checklists');
  clEl.innerHTML = (card.checklists || []).map(cl => `
    <div class="checklist-block" data-cl="${cl.id}">
      <strong>${esc(cl.title)}</strong>
      ${(cl.items || []).map(it => `
        <div class="checklist-item">
          <input type="checkbox" ${it.is_checked ? 'checked' : ''} data-item="${it.id}">
          <span>${esc(it.text)}</span>
        </div>
      `).join('')}
      <form data-add-item="${cl.id}" class="add-item-form">
        <input type="text" placeholder="Novo item…" required>
        <button class="btn btn-sm">Add</button>
      </form>
    </div>
  `).join('');
  clEl.querySelectorAll('input[type=checkbox]').forEach(cb => {
    cb.onchange = async () => {
      await fetch(`/api/checklist-items/${cb.dataset.item}`, {
        method: 'PATCH', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_checked: cb.checked })
      });
      reloadBoard();
    };
  });
  clEl.querySelectorAll('.add-item-form').forEach(f => {
    f.onsubmit = async (e) => {
      e.preventDefault();
      const text = f.querySelector('input').value;
      await fetch(`/api/checklists/${f.dataset.addItem}/items`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      openCard(card.id);
    };
  });

  document.getElementById('modal-comments').innerHTML = (card.comments || []).map(c =>
    `<div class="comment-item">${esc(c.body)} <span class="muted">· ${c.created_at.slice(0, 16)}</span></div>`
  ).join('');

  document.getElementById('card-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('card-modal').classList.add('hidden');
  reloadBoard();
}

async function saveCardTitle() {
  const id = document.getElementById('modal-card-id').value;
  const title = document.getElementById('modal-title').textContent.trim();
  if (!title) return;
  await fetch(`/api/cards/${id}`, {
    method: 'PATCH', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
}

async function saveCardDesc() {
  const id = document.getElementById('modal-card-id').value;
  await fetch(`/api/cards/${id}`, {
    method: 'PATCH', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ description: document.getElementById('modal-desc').value })
  });
}

async function saveCardDue() {
  const id = document.getElementById('modal-card-id').value;
  const v = document.getElementById('modal-due').value;
  await fetch(`/api/cards/${id}`, {
    method: 'PATCH', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ due_date: v ? new Date(v).toISOString() : null })
  });
}

async function addChecklist() {
  const id = document.getElementById('modal-card-id').value;
  await fetch(`/api/cards/${id}/checklists`, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Checklist' })
  });
  openCard(parseInt(id));
}

async function submitComment(e) {
  e.preventDefault();
  const id = document.getElementById('modal-card-id').value;
  const body = document.getElementById('comment-body').value;
  await fetch(`/api/cards/${id}/comments`, {
    method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ body })
  });
  document.getElementById('comment-body').value = '';
  openCard(parseInt(id));
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}
