(function () {
  // ======================
  // FILTROS
  // ======================
  const cedulaInput = document.getElementById('filterCedula');
  const nombreInput = document.getElementById('filterNombre');
  const rolFilterSelect = document.getElementById('filterRol');
  const estadoFilterSelect = document.getElementById('filterEstado');
  const rows = document.querySelectorAll('#usersTable tbody .urow');

  function applyFilters() {
    const fc = (cedulaInput?.value || '').toLowerCase().trim();
    const fn = (nombreInput?.value || '').toLowerCase().trim();
    const fr = (rolFilterSelect?.value || '').toUpperCase().trim(); // rol elegido
    const fe = (estadoFilterSelect?.value || '').trim();            // "true"/"false" o ""

    rows.forEach(r => {
      const ced = r.dataset.cedula || '';
      const full = r.dataset.fullname || '';
      const rol = (r.dataset.rol || '').toUpperCase();
      const est = (r.dataset.estado || '').trim();

      const okCed = !fc || ced.includes(fc);
      const okNom = !fn || full.includes(fn);

      const okRol = !fr || rol === fr;
      const okEst = !fe || est === fe;

      r.style.display = (okCed && okNom && okRol && okEst) ? '' : 'none';
    });
  }

  cedulaInput?.addEventListener('input', applyFilters);
  nombreInput?.addEventListener('input', applyFilters);
  rolFilterSelect?.addEventListener('change', applyFilters);
  estadoFilterSelect?.addEventListener('change', applyFilters);

  // ======================
  // MODAL
  // ======================
  const modal = document.getElementById('editModal');
  const modalClose = document.getElementById('modalClose');
  const modalBackdrop = document.getElementById('modalBackdrop');

  const idInput = document.getElementById('m_id_usuario');
  const idPw = document.getElementById('m_id_usuario_pw');
  const cedulaSpan = document.getElementById('m_cedula');
  const nombreSpan = document.getElementById('m_nombre');

  const rolModalSelect = document.getElementById('m_rol');
  const btnSaveRol = document.getElementById('btnSaveRol');

  const badgeSelf = document.getElementById('m_self_badge');
  const msgSelf = document.getElementById('selfRoleMsg');

  const pwInput = document.getElementById('m_new_password');

  function openModal() {
    modal?.classList.remove('hidden');
  }

  function closeModal() {
    modal?.classList.add('hidden');
    if (pwInput) pwInput.value = '';
  }

  modalClose?.addEventListener('click', closeModal);
  modalBackdrop?.addEventListener('click', closeModal);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal && !modal.classList.contains('hidden')) closeModal();
  });

  // Abrir modal con datos
  document.querySelectorAll('[data-action="edit"]').forEach(btn => {
    btn.addEventListener('click', () => {
      const tr = btn.closest('tr');
      if (!tr) return;

      const id = tr.dataset.id || '';
      const ced = (tr.querySelector('.cedula')?.textContent || '').trim();
      const nom = (tr.querySelector('.nombre')?.textContent || '').trim();
      const ape = (tr.querySelector('.apellido')?.textContent || '').trim();
      const rol = tr.dataset.rol || '';
      const isSelf = tr.dataset.self === 'true';

      if (idInput) idInput.value = id;
      if (idPw) idPw.value = id;

      if (cedulaSpan) cedulaSpan.textContent = ced;
      if (nombreSpan) nombreSpan.textContent = (nom + ' ' + ape).trim();

      if (rolModalSelect && rol) rolModalSelect.value = rol;

      // UI: si es mi usuario, bloquear cambio de rol
      if (isSelf) {
        badgeSelf?.classList.remove('hidden');
        msgSelf?.classList.remove('hidden');

        if (rolModalSelect) rolModalSelect.disabled = true;
        if (btnSaveRol) {
          btnSaveRol.disabled = true;
          btnSaveRol.classList.add('is-disabled');
        }
      } else {
        badgeSelf?.classList.add('hidden');
        msgSelf?.classList.add('hidden');

        if (rolModalSelect) rolModalSelect.disabled = false;
        if (btnSaveRol) {
          btnSaveRol.disabled = false;
          btnSaveRol.classList.remove('is-disabled');
        }
      }

      openModal();
    });
  });

})();
