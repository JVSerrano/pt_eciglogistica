// Lógica de la página: pestañas (y más adelante listado y formulario)
(function () {
  'use strict';

  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));

  // Muestra la pestaña indicada y oculta las demás
  function selectTab(selected, setFocus) {
    tabs.forEach(function (tab) {
      var isSelected = tab === selected;
      var panel = document.getElementById(tab.getAttribute('aria-controls'));

      tab.classList.toggle('is-active', isSelected);
      tab.setAttribute('aria-selected', isSelected ? 'true' : 'false');
      // Solo la pestaña activa entra en el orden del tabulador
      tab.tabIndex = isSelected ? 0 : -1;
      panel.hidden = !isSelected;
    });

    if (setFocus) {
      selected.focus();
    }

    // Al abrir el listado se pide la lista a la API para que esté al día
    if (selected.id === 'tab-list') {
      loadList();
    }
  }

  // ---------- Listado ----------

  var LIST_URL = '/api/consultations.php';
  var STATUS_TEXT = {
    pending: 'Pendiente',
    classified: 'Clasificada',
    error: 'Error'
  };

  // Texto de quién decidió el departamento (la IA o las palabras clave)
  var METHOD_TEXT = {
    gemini: 'IA',
    keywords: 'Palabras clave'
  };

  // Clase de color de cada departamento (los colores están en el CSS)
  var DEPARTMENT_CLASS = {
    'Soporte Técnico': 'dept-support',
    'Comercial': 'dept-sales',
    'Agradecimientos': 'dept-thanks'
  };

  var MONTHS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];

  var loadingEl = document.getElementById('list-loading');
  var emptyEl = document.getElementById('list-empty');
  var errorEl = document.getElementById('list-error');
  var tableWrapEl = document.getElementById('table-wrap');
  var listBodyEl = document.getElementById('list-body');
  var refreshBtn = document.getElementById('refresh-btn');
  var retryBtn = document.getElementById('retry-btn');

  // Evita pedir la lista dos veces a la vez
  var isLoadingList = false;

  // Enseña solo uno de los estados: 'loading', 'empty', 'error' o 'table'
  function showListState(state) {
    loadingEl.hidden = state !== 'loading';
    emptyEl.hidden = state !== 'empty';
    errorEl.hidden = state !== 'error';
    tableWrapEl.hidden = state !== 'table';
  }

  // Crea una celda de la tabla. Los datos de la API se escriben con textContent (nunca innerHTML)
  // El label se usa en móvil: el CSS lo enseña delante del valor (atributo data-label)
  function createCell(label, text, className) {
    var td = document.createElement('td');
    td.textContent = text;
    td.setAttribute('data-label', label);
    if (className) {
      td.className = className;
    }
    return td;
  }

  // Celda con una pastilla de color dentro (departamento y estado)
  function createBadgeCell(label, text, badgeClass) {
    var td = createCell(label, '', 'nowrap');
    var badge = document.createElement('span');
    badge.className = 'badge ' + badgeClass;
    badge.textContent = text;
    td.appendChild(badge);
    return td;
  }

  // Pasa "2026-11-11 17:28:35" a "11/11/2026 17:28:35" (solo reordena el texto, sin zonas horarias)
  function formatDate(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2}:\d{2})/.exec(value || '');
    if (!match) {
      return value || '—'; // formato inesperado: se enseña tal cual
    }
    return match[3] + '/' + match[2] + '/' + match[1] + ' ' + match[4];
  }

  // Pasa "2026-11-11 17:28:35" a "11 nov, 17:28" (con el año si no es el actual)
  function formatShortDate(value) {
    var match = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/.exec(value || '');
    if (!match) {
      return value || '—';
    }
    var year = match[1] === String(new Date().getFullYear()) ? '' : ' ' + match[1];
    return parseInt(match[3], 10) + ' ' + MONTHS[parseInt(match[2], 10) - 1] + year + ', ' + match[4];
  }

  // Celda del mensaje: texto recortado a 3 líneas y un botón para expandir o contraer
  function createMessageCell(text) {
    var td = document.createElement('td');
    var wrapper = document.createElement('div');
    var textEl = document.createElement('div');
    var toggleBtn = document.createElement('button');

    td.setAttribute('data-label', 'Mensaje');
    td.className = 'message';
    wrapper.className = 'msg-cell';

    textEl.className = 'msg-text is-collapsed';
    textEl.textContent = text;

    toggleBtn.type = 'button';
    toggleBtn.className = 'msg-toggle';
    toggleBtn.textContent = 'Mostrar más';
    toggleBtn.setAttribute('aria-expanded', 'false');
    toggleBtn.hidden = true; // solo se enseña si el texto no cabe (ver updateToggles)

    toggleBtn.addEventListener('click', function () {
      var collapsed = textEl.classList.toggle('is-collapsed');
      toggleBtn.textContent = collapsed ? 'Mostrar más' : 'Mostrar menos';
      toggleBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    });

    wrapper.appendChild(textEl);
    wrapper.appendChild(toggleBtn);
    td.appendChild(wrapper);
    return td;
  }

  // Enseña el botón solo en los mensajes recortados de verdad.
  // Los mensajes expandidos conservan su botón para poder contraerlos.
  function updateToggles() {
    var cells = listBodyEl.querySelectorAll('.msg-cell');

    Array.prototype.forEach.call(cells, function (cell) {
      var textEl = cell.querySelector('.msg-text');
      var toggleBtn = cell.querySelector('.msg-toggle');

      if (textEl.classList.contains('is-collapsed')) {
        toggleBtn.hidden = textEl.scrollHeight <= textEl.clientHeight + 1;
      }
    });
  }

  // Al cambiar el ancho de la ventana cambia qué mensajes caben
  window.addEventListener('resize', updateToggles);

  function renderList(consultations) {
    listBodyEl.textContent = ''; // vacía la tabla

    consultations.forEach(function (item) {
      var tr = document.createElement('tr');
      var status = STATUS_TEXT[item.status] || item.status;
      // Sin método (pendiente o con error) se muestra un guion
      var method = item.classified_by ? (METHOD_TEXT[item.classified_by] || item.classified_by) : '—';

      var deptClass = DEPARTMENT_CLASS[item.department];

      // El color de la fila depende del departamento (sin departamento, la fila queda neutra)
      if (deptClass) {
        tr.className = deptClass;
      }

      tr.appendChild(createCell('Nombre', item.client_name, 'name'));
      tr.appendChild(createMessageCell(item.message));
      if (item.department) {
        tr.appendChild(createBadgeCell('Departamento', item.department, 'badge-dept'));
      } else {
        tr.appendChild(createCell('Departamento', '—', 'nowrap'));
      }
      tr.appendChild(createCell('Clasificado por', method, 'nowrap muted'));
      tr.appendChild(createBadgeCell('Estado', status, 'badge-status-' + item.status));

      // Fecha corta a la vista; la completa queda en el atributo title
      var dateCell = createCell('Fecha / hora', formatShortDate(item.created_at), 'nowrap');
      dateCell.title = formatDate(item.created_at);
      tr.appendChild(dateCell);

      listBodyEl.appendChild(tr);
    });
  }

  function loadList() {
    if (isLoadingList) {
      return;
    }
    isLoadingList = true;
    refreshBtn.disabled = true;
    showListState('loading');

    fetch(LIST_URL)
      .then(function (response) {
        if (!response.ok) {
          throw new Error('bad status');
        }
        return response.json();
      })
      .then(function (data) {
        if (!data || !Array.isArray(data.consultations)) {
          throw new Error('bad data');
        }
        if (data.consultations.length === 0) {
          showListState('empty');
        } else {
          renderList(data.consultations);
          showListState('table');
          updateToggles(); // se mide después de mostrar la tabla
        }
      })
      .catch(function () {
        showListState('error');
      })
      .then(function () {
        isLoadingList = false;
        refreshBtn.disabled = false;
      });
  }

  refreshBtn.addEventListener('click', loadList);
  retryBtn.addEventListener('click', loadList);

  // ---------- Formulario ----------

  var SEND_TIMEOUT_MS = 20000; // la API espera como mucho 15 s al clasificador
  var MAX_NAME = 100;
  var MAX_MESSAGE = 2000;

  var formEl = document.getElementById('consultation-form');
  var nameInput = document.getElementById('client-name');
  var messageInput = document.getElementById('message');
  var nameErrorEl = document.getElementById('client-name-error');
  var messageErrorEl = document.getElementById('message-error');
  var submitBtn = document.getElementById('submit-btn');

  // Bloqueo contra envíos dobles (además del botón desactivado)
  var isSending = false;

  // Enseña u oculta el aviso de un campo
  function setFieldError(input, errorEl, text) {
    errorEl.textContent = text;
    errorEl.hidden = text === '';
    input.setAttribute('aria-invalid', text === '' ? 'false' : 'true');
  }

  // Devuelve el texto de error de un campo, o '' si es válido
  function validateText(value, maxLength, label) {
    if (value === '') {
      return 'Escribe ' + label + '.';
    }
    if (value.length > maxLength) {
      return 'Máximo ' + maxLength + ' caracteres.';
    }
    return '';
  }

  // Validación solo por comodidad: la API repite todas las comprobaciones
  function validateForm() {
    var nameError = validateText(nameInput.value.trim(), MAX_NAME, 'tu nombre');
    var messageError = validateText(messageInput.value.trim(), MAX_MESSAGE, 'un mensaje');

    setFieldError(nameInput, nameErrorEl, nameError);
    setFieldError(messageInput, messageErrorEl, messageError);

    // Lleva el foco al primer campo con fallo
    if (nameError) {
      nameInput.focus();
    } else if (messageError) {
      messageInput.focus();
    }

    return nameError === '' && messageError === '';
  }

  // Activa o desactiva el estado "Enviando..."
  function setSending(sending) {
    isSending = sending;
    submitBtn.disabled = sending;
    submitBtn.textContent = sending ? 'Enviando...' : 'Enviar';
  }

  // Envía la consulta y devuelve una promesa con la respuesta ya interpretada:
  // { kind: 'ok', httpStatus, consultation } o { kind: 'timeout' | 'network' | 'http', httpStatus }
  function sendConsultation(clientName, message) {
    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, SEND_TIMEOUT_MS);

    return fetch(LIST_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ client_name: clientName, message: message }),
      signal: controller.signal
    })
      .then(function (response) {
        // Si la respuesta no es JSON (por ejemplo una página de error de Apache), data queda en null
        return response.json().then(
          function (data) { return { response: response, data: data }; },
          function () { return { response: response, data: null }; }
        );
      })
      .then(function (result) {
        var httpStatus = result.response.status;
        if (httpStatus === 201 && result.data && result.data.consultation) {
          return { kind: 'ok', httpStatus: httpStatus, consultation: result.data.consultation };
        }
        return { kind: 'http', httpStatus: httpStatus };
      })
      .catch(function (error) {
        // AbortError = se agotó el tiempo; cualquier otro fallo = sin conexión
        if (error && error.name === 'AbortError') {
          return { kind: 'timeout' };
        }
        return { kind: 'network' };
      })
      .then(function (outcome) {
        clearTimeout(timer);
        return outcome;
      });
  }

  var resultEl = document.getElementById('form-result');

  // Muestra un toast y copia el texto a la zona aria-live para los lectores de pantalla
  function showMessage(text, isError, duration) {
    Toastify({
      text: text, // Toastify lo escribe como texto, no como HTML
      duration: duration || 5000,
      gravity: 'bottom',
      position: 'center',
      close: true,
      style: {
        background: isError ? '#DE2C37' : '#ffffff',
        color: isError ? '#ffffff' : '#222222',
        border: '2px solid #DE2C37',
        boxShadow: '0 3px 8px rgba(0, 0, 0, 0.25)'
      }
    }).showToast();

    resultEl.textContent = text;
  }

  // Decide el mensaje según el resultado. Nunca se enseña el texto de error de la API
  function handleOutcome(outcome) {
    if (outcome.kind === 'ok') {
      var consultation = outcome.consultation;

      // La API responde 201 también si la consulta queda en error: se mira "status"
      if (consultation.status === 'classified' && consultation.department) {
        showMessage('Consulta enviada al departamento ' + consultation.department + '.', false);
      } else {
        showMessage('Ha habido un error. La consulta se ha guardado, pero no se ha podido clasificar.', true);
      }
    } else if (outcome.kind === 'timeout') {
      showMessage('La respuesta tarda demasiado. Mira el listado antes de volver a enviar, por si la consulta ya se guardó.', true, 8000);
    } else if (outcome.kind === 'network') {
      showMessage('No se ha podido conectar con el servidor.', true);
    } else if (outcome.httpStatus === 400 || outcome.httpStatus === 422) {
      showMessage('Revisa el nombre y el mensaje e inténtalo de nuevo.', true);
    } else {
      showMessage('No se ha podido enviar la consulta. Inténtalo de nuevo.', true);
    }
  }

  formEl.addEventListener('submit', function (event) {
    event.preventDefault();

    if (isSending || !validateForm()) {
      return;
    }

    setSending(true);

    sendConsultation(nameInput.value.trim(), messageInput.value.trim()).then(function (outcome) {
      // Solo se vacía el formulario si la consulta se ha guardado; si falla se conserva lo escrito
      if (outcome.kind === 'ok') {
        formEl.reset();
      }
      handleOutcome(outcome);
      setSending(false);
    });
  });

  tabs.forEach(function (tab, index) {
    // Cambio con el ratón
    tab.addEventListener('click', function () {
      selectTab(tab, false);
    });

    // Cambio con el teclado: flechas, Inicio y Fin
    tab.addEventListener('keydown', function (event) {
      var next = null;

      if (event.key === 'ArrowRight') {
        next = tabs[(index + 1) % tabs.length];
      } else if (event.key === 'ArrowLeft') {
        next = tabs[(index - 1 + tabs.length) % tabs.length];
      } else if (event.key === 'Home') {
        next = tabs[0];
      } else if (event.key === 'End') {
        next = tabs[tabs.length - 1];
      }

      if (next) {
        event.preventDefault();
        selectTab(next, true);
      }
    });
  });
})();
