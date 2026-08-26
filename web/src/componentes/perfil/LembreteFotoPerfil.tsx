import { useRef, useState } from 'react';
import { Dialogo } from '../dialogos/Dialogo';
import { calcularExibicao, clampOffset, retanguloDeRecorte } from '../../dominio/fotoPerfil';
import type { Dimensoes, Offset } from '../../dominio/fotoPerfil';
import { useSalvarMinhaFoto } from '../../hooks/mutacoes';
import * as sessao from '../../servicos/sessao';

// O pedido de foto no primeiro acesso (docs/sprints.html · SPRINT FOTO · P2)
// e o "quem já tinha conta mas nunca mandou uma" (P3) viram UM mecanismo só:
// login e primeiro-acesso devolvem `temFoto`, e este componente mostra o
// mesmo diálogo sempre que `temFoto` for false — não importa se a conta
// nasceu agora ou há um ano. "Agora não" some pelo resto da sessão
// (sessionStorage) e volta no próximo login, até a pessoa mandar uma foto.
//
// A matemática do recorte (cover, zoom, arrasto) é pura e mora em
// src/dominio/fotoPerfil.ts, com teste ao lado — aqui só o que precisa de
// DOM: <canvas> pra desenhar e FileReader pra virar base64.

const TAMANHO_VIEWPORT = 240;
const TAMANHO_SAIDA = 512;
const ZOOM_MIN = 1;
const ZOOM_MAX = 2.5;
const TIPOS_ACEITOS = ['image/jpeg', 'image/png', 'image/webp'];

function blobParaBase64(blob: Blob): Promise<string> {
  return new Promise((resolver, rejeitar) => {
    const leitor = new FileReader();
    leitor.onload = () => resolver(String(leitor.result).split(',', 2)[1] ?? '');
    leitor.onerror = () => rejeitar(new Error('Não consegui ler a imagem cropada.'));
    leitor.readAsDataURL(blob);
  });
}

function croparParaBlob(img: HTMLImageElement, dim: Dimensoes, zoom: number, offset: Offset): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = TAMANHO_SAIDA;
  canvas.height = TAMANHO_SAIDA;
  const ctx = canvas.getContext('2d');
  if (!ctx) return Promise.reject(new Error('Este navegador não suporta o recorte da imagem.'));

  const { x, y, largura, altura } = retanguloDeRecorte(dim, zoom, offset, TAMANHO_VIEWPORT, TAMANHO_SAIDA);
  ctx.drawImage(img, x, y, largura, altura);

  return new Promise((resolver, rejeitar) => {
    canvas.toBlob(
      (blob) => (blob ? resolver(blob) : rejeitar(new Error('Não consegui gerar a imagem recortada.'))),
      'image/jpeg',
      0.85,
    );
  });
}

export function LembreteFotoPerfil() {
  const [dispensado, setDispensado] = useState(false);
  const [urlImagem, setUrlImagem] = useState<string | null>(null);
  const [dimensoes, setDimensoes] = useState<Dimensoes | null>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<Offset>({ x: 0, y: 0 });
  const [autorizado, setAutorizado] = useState(false);
  const [erro, setErro] = useState('');

  const imgRef = useRef<HTMLImageElement | null>(null);
  const arrastoRef = useRef<{ x: number; y: number; offset: Offset } | null>(null);
  const salvar = useSalvarMinhaFoto();

  if (!sessao.autenticado() || sessao.temFoto() || dispensado || sessao.fotoFoiDispensadaNestaSessao()) {
    return null;
  }

  function limparArquivo() {
    if (urlImagem) URL.revokeObjectURL(urlImagem);
    setUrlImagem(null);
    setDimensoes(null);
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }

  function agoraNao() {
    sessao.dispensarFotoNestaSessao();
    setDispensado(true);
  }

  function selecionarArquivo(ev: React.ChangeEvent<HTMLInputElement>) {
    const f = ev.target.files?.[0] ?? null;
    ev.target.value = '';
    if (!f) return;
    setErro('');
    if (!TIPOS_ACEITOS.includes(f.type)) {
      setErro('Envie uma imagem JPEG, PNG ou WebP.');
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setErro('Essa imagem é grande demais (máximo 20 MB).');
      return;
    }
    if (urlImagem) URL.revokeObjectURL(urlImagem);
    setUrlImagem(URL.createObjectURL(f));
    setDimensoes(null);
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }

  function aoCarregarImagem(ev: React.SyntheticEvent<HTMLImageElement>) {
    setDimensoes({ w: ev.currentTarget.naturalWidth, h: ev.currentTarget.naturalHeight });
  }

  function aoMudarZoom(ev: React.ChangeEvent<HTMLInputElement>) {
    const novoZoom = Number(ev.target.value);
    setZoom(novoZoom);
    if (dimensoes) setOffset((o) => clampOffset(o, dimensoes, novoZoom, TAMANHO_VIEWPORT));
  }

  function aoIniciarArrasto(ev: React.PointerEvent<HTMLDivElement>) {
    if (!dimensoes) return;
    ev.currentTarget.setPointerCapture(ev.pointerId);
    arrastoRef.current = { x: ev.clientX, y: ev.clientY, offset };
  }

  function aoMoverArrasto(ev: React.PointerEvent<HTMLDivElement>) {
    const inicio = arrastoRef.current;
    if (!inicio || !dimensoes) return;
    setOffset(
      clampOffset(
        { x: inicio.offset.x + (ev.clientX - inicio.x), y: inicio.offset.y + (ev.clientY - inicio.y) },
        dimensoes,
        zoom,
        TAMANHO_VIEWPORT,
      ),
    );
  }

  function aoSoltarArrasto() {
    arrastoRef.current = null;
  }

  async function confirmar() {
    if (!imgRef.current || !dimensoes) return;
    if (!autorizado) {
      setErro('Confirme abaixo que pode enviar esta foto para continuar.');
      return;
    }
    setErro('');
    try {
      const blob = await croparParaBlob(imgRef.current, dimensoes, zoom, offset);
      const conteudoBase64 = await blobParaBase64(blob);
      await salvar.mutateAsync({
        conteudo_base64: conteudoBase64,
        content_type: 'image/jpeg',
        declaracao_autorizacao: true,
      });
      sessao.marcarFotoDefinida();
      setDispensado(true);
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível salvar a foto.');
    }
  }

  const { largura: larguraExibida, altura: alturaExibida } = dimensoes
    ? calcularExibicao(dimensoes, zoom, TAMANHO_VIEWPORT)
    : { largura: 0, altura: 0 };

  return (
    <Dialogo
      titulo="Adicionar foto de perfil"
      subtitulo="Ajuda a coordenação e você a se reconhecerem no SAS. Pode enviar agora ou deixar para depois."
      onFechar={agoraNao}
      rodape={
        <>
          <button type="button" className="btn btn--ghost" onClick={agoraNao} disabled={salvar.isPending}>
            Agora não
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={confirmar}
            disabled={!urlImagem || salvar.isPending}
          >
            {salvar.isPending ? 'Enviando…' : 'Salvar foto'}
          </button>
        </>
      }
    >
      {!urlImagem ? (
        <label className="foto-editor__escolher">
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={selecionarArquivo}
            className="foto-editor__input-arquivo"
          />
          <span>Escolher foto</span>
          <span className="foto-editor__dica">No celular, sua câmera aparece como opção.</span>
        </label>
      ) : (
        <div className="foto-editor__corpo">
          <div
            className="foto-editor__viewport"
            style={{ width: TAMANHO_VIEWPORT, height: TAMANHO_VIEWPORT }}
            onPointerDown={aoIniciarArrasto}
            onPointerMove={aoMoverArrasto}
            onPointerUp={aoSoltarArrasto}
            onPointerCancel={aoSoltarArrasto}
          >
            <img
              ref={imgRef}
              src={urlImagem}
              alt="Prévia da foto a recortar"
              onLoad={aoCarregarImagem}
              className="foto-editor__imagem"
              style={
                dimensoes
                  ? {
                      width: larguraExibida,
                      height: alturaExibida,
                      transform: `translate(${offset.x - larguraExibida / 2 + TAMANHO_VIEWPORT / 2}px, ${offset.y - alturaExibida / 2 + TAMANHO_VIEWPORT / 2}px)`,
                    }
                  : undefined
              }
              draggable={false}
            />
          </div>

          <input
            type="range"
            className="foto-editor__zoom"
            min={ZOOM_MIN}
            max={ZOOM_MAX}
            step={0.05}
            value={zoom}
            onChange={aoMudarZoom}
            aria-label="Zoom da foto"
          />

          <button type="button" className="btn btn--ghost foto-editor__trocar" onClick={limparArquivo}>
            Trocar foto
          </button>

          <label className="foto-editor__autorizacao">
            <input
              type="checkbox"
              checked={autorizado}
              onChange={(ev) => setAutorizado(ev.target.checked)}
            />
            <span>
              {sessao.tipo() === 'aluno'
                ? 'Confirmo que posso enviar esta foto (a minha, ou a de um aluno sob minha responsabilidade).'
                : 'Confirmo que posso enviar esta foto.'}
            </span>
          </label>
        </div>
      )}

      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
