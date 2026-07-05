import { httpClient } from './services/http-client.js';

// Configuração dos dois modos (aluno / coordenador)
const MODOS = {
  aluno: {
    label:         'Acesso · aluno',
    hl1:           'Sua jornada,',
    hlEm:          'medida',
    hl2:           ' a cada passo.',
    subtitle:      'Veja cada simulado, cada nota e cada avanço até a sua aprovação. Sua devolutiva, sua evolução, seu painel.',
    fieldLabel:    'Matrícula',
    placeholder:   'matrícula ou e-mail institucional',
    submitText:    'Entrar no painel do aluno',
    rightHl:       'A tradição que aprova.<br>Agora, acompanhada<br>com <em>precisão.</em>',
    rightSub:      'Cada simulado ganha contexto, cada nota vira direção e cada aluno acompanha sua evolução até a aprovação.',
  },
  coordenador: {
    label:         'Acesso · coordenação',
    hl1:           'Gestão clara,',
    hlEm:          'decisões',
    hl2:           ' com profundidade.',
    subtitle:      'Acompanhe dados individuais e gerais, compare turmas, ciclos e desempenhos, identifique alertas e transforme informação em ação pedagógica.',
    fieldLabel:    'Usuário',
    placeholder:   'usuário institucional',
    submitText:    'Entrar no painel da coordenação',
    rightHl:       'Diagnóstico que organiza<br>a visão. Dados que orientam<br>a <em>decisão.</em>',
    rightSub:      'Do aluno individual ao panorama da rede, a plataforma cruza resultados, evidencia prioridades e apoia intervenções pedagógicas com clareza.',
  },
};

let modoAtual = 'aluno';
let emTransicao = false;

// ─── Elementos ────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const els = {
  label:       $('js-label'),
  hl1:         $('js-hl-line1'),
  hlEm:        $('js-hl-em'),
  hl2:         $('js-hl-line2'),
  subtitle:    $('js-subtitle'),
  fieldLabel:  $('js-field-label'),
  inputUser:   $('js-input-user'),
  inputSenha:  $('js-input-senha'),
  submitText:  $('js-submit-text'),
  btnAluno:    $('btn-aluno'),
  btnCoord:    $('btn-coord'),
  rightHl:     $('js-right-headline'),
  rightSub:    $('js-right-sub'),
  rightHero:   $('js-right-hero'),
  error:       $('js-error'),
  eyeIcon:     $('js-eye-icon'),
};

// Blocos que animam durante a transição
const FADE_TARGETS = [
  document.querySelector('.lp-label'),
  document.querySelector('.lp-headline-wrap'),
  document.querySelector('.lp-subtitle'),
  els.rightHero,
];

// ─── Trocar modo ──────────────────────────────────────────────────────────
function setModo(modo) {
  if (modo === modoAtual || emTransicao) return;
  emTransicao = true;

  // Botões mudam imediatamente com transição CSS suave
  els.btnAluno.classList.toggle('is-active', modo === 'aluno');
  els.btnCoord.classList.toggle('is-active', modo === 'coordenador');

  // Fase 1: fade out + slide down
  FADE_TARGETS.forEach((el) => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(10px)';
  });

  setTimeout(() => {
    const m = MODOS[modo];

    // Atualizar conteúdo esquerdo
    els.label.textContent       = m.label;
    els.hl1.textContent         = m.hl1;
    els.hlEm.textContent        = m.hlEm;
    els.hl2.textContent         = m.hl2;
    els.subtitle.textContent    = m.subtitle;
    els.fieldLabel.textContent  = m.fieldLabel;
    els.inputUser.placeholder   = m.placeholder;
    els.submitText.textContent  = m.submitText;
    els.error.style.display     = 'none';
    els.inputUser.value         = '';
    els.inputSenha.value        = '';

    // Atualizar conteúdo direito
    els.rightHl.innerHTML  = m.rightHl;
    els.rightSub.textContent = m.rightSub;

    modoAtual = modo;

    // Fase 2: fade in + slide up
    FADE_TARGETS.forEach((el) => {
      el.style.opacity   = '1';
      el.style.transform = 'translateY(0)';
    });

    setTimeout(() => { emTransicao = false; }, 240);
  }, 200);
}

// ─── Submissão ────────────────────────────────────────────────────────────
async function handleSubmit(e) {
  e.preventDefault();
  const user = els.inputUser.value.trim();
  const pass = els.inputSenha.value;

  const submitBtn = document.getElementById('js-submit');
  submitBtn.disabled = true;
  els.error.style.display = 'none';

  try {
    const res = await fetch(`${httpClient.baseUrl()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tipo: modoAtual, usuario: user, senha: pass }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Credenciais inválidas. Verifique seus dados e tente novamente.');
    }

    const dados = await res.json();
    sessionStorage.setItem('sas_token',    dados.access_token);
    sessionStorage.setItem('sas_tipo',     dados.tipo);
    sessionStorage.setItem('sas_nome',     dados.nome);
    sessionStorage.setItem('sas_auth',     '1');
    if (dados.aluno_id) sessionStorage.setItem('sas_aluno_id', dados.aluno_id);

    window.location.href = './index.html';
  } catch (err) {
    els.error.style.display = 'block';
    els.error.textContent   = err.message || 'Credenciais inválidas. Verifique seus dados e tente novamente.';
    const form = document.getElementById('js-form');
    form.style.animation = 'none';
    void form.offsetHeight;
    form.style.animation = 'lp-shake 0.4s ease';
  } finally {
    submitBtn.disabled = false;
  }
}

// ─── Primeiro acesso / esqueci minha senha ────────────────────────────────
// Valida RA + e-mail do Canvas no backend e cria a senha na hora.

function _alternarFormularios(mostrarPrimeiroAcesso) {
  document.getElementById('js-form').style.display = mostrarPrimeiroAcesso ? 'none' : '';
  document.getElementById('js-form-pa').style.display = mostrarPrimeiroAcesso ? '' : 'none';
  document.getElementById('js-first-access-wrap').style.display = mostrarPrimeiroAcesso ? 'none' : '';
  els.error.style.display = 'none';
  document.getElementById('js-pa-error').style.display = 'none';
  if (mostrarPrimeiroAcesso && modoAtual !== 'aluno') setModo('aluno');
}

async function handlePrimeiroAcesso(e) {
  e.preventDefault();
  const erroEl = document.getElementById('js-pa-error');
  const submitBtn = document.getElementById('js-pa-submit');
  const matricula = document.getElementById('js-pa-matricula').value.trim();
  const email = document.getElementById('js-pa-email').value.trim();
  const senha = document.getElementById('js-pa-senha').value;
  const confirmar = document.getElementById('js-pa-confirmar').value;

  erroEl.style.display = 'none';

  const mostrarErro = (msg) => {
    erroEl.style.display = 'block';
    erroEl.textContent = msg;
  };

  if (!matricula || !email) return mostrarErro('Preencha matrícula e e-mail.');
  if (senha.length < 8) return mostrarErro('A senha precisa ter pelo menos 8 caracteres.');
  if (senha !== confirmar) return mostrarErro('As senhas não conferem.');

  submitBtn.disabled = true;
  try {
    const res = await fetch(`${httpClient.baseUrl()}/auth/primeiro-acesso`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ matricula, email, senha_nova: senha }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detalhe = typeof err.detail === 'string' ? err.detail : '';
      throw new Error(detalhe || 'Não foi possível validar seus dados.');
    }

    // Mesmo shape do login — entra direto na área do aluno.
    const dados = await res.json();
    sessionStorage.setItem('sas_token', dados.access_token);
    sessionStorage.setItem('sas_tipo',  dados.tipo);
    sessionStorage.setItem('sas_nome',  dados.nome);
    sessionStorage.setItem('sas_auth',  '1');
    if (dados.aluno_id) sessionStorage.setItem('sas_aluno_id', dados.aluno_id);
    window.location.href = './index.html';
  } catch (err) {
    mostrarErro(err.message || 'Não foi possível validar seus dados.');
  } finally {
    submitBtn.disabled = false;
  }
}

// ─── Toggle senha visível ─────────────────────────────────────────────────
function toggleSenha() {
  const input = els.inputSenha;
  if (input.type === 'password') {
    input.type = 'text';
    els.eyeIcon.innerHTML = `
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>`;
  } else {
    input.type = 'password';
    els.eyeIcon.innerHTML = `
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>`;
  }
}

// ─── Listeners (o script é module — sem handlers inline no HTML) ─────────
els.btnAluno.addEventListener('click', () => setModo('aluno'));
els.btnCoord.addEventListener('click', () => setModo('coordenador'));
$('js-form').addEventListener('submit', handleSubmit);
$('js-eye-btn').addEventListener('click', toggleSenha);
$('js-form-pa').addEventListener('submit', handlePrimeiroAcesso);
$('js-primeiro-acesso').addEventListener('click', (e) => { e.preventDefault(); _alternarFormularios(true); });
$('js-esqueci').addEventListener('click', (e) => { e.preventDefault(); _alternarFormularios(true); });
$('js-pa-voltar').addEventListener('click', (e) => { e.preventDefault(); _alternarFormularios(false); });

// ─── Animação de shake (erro de login) ───────────────────────────────────
const style = document.createElement('style');
style.textContent = `
  @keyframes lp-shake {
    0%  { transform: translateX(0); }
    20% { transform: translateX(-6px); }
    40% { transform: translateX(6px); }
    60% { transform: translateX(-4px); }
    80% { transform: translateX(4px); }
    100%{ transform: translateX(0); }
  }
`;
document.head.appendChild(style);
