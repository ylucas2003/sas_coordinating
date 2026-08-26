import { useEffect, useRef, useState } from 'react';
import { useFotoPerfil } from '../../hooks/consultas';

// Avatar com foto de perfil, e a inicial do nome como fallback — o mesmo
// círculo que `alu-avatar`/`topbar__avatar` já desenhavam, agora com uma
// <img> por cima quando a pessoa tem foto (docs/sprints.html · SPRINT FOTO).
//
// A busca da foto só liga depois que o próprio elemento entra na viewport
// (IntersectionObserver, uma vez só). Numa lista de ~900 alunos isso é o que
// evita 900 requisições no primeiro render — só quem a pessoa rolou até ver
// chega a pedir a foto, e só se `temFoto` já sinalizar que existe uma.

interface Props {
  tipo: 'aluno' | 'coordenador';
  nome: string;
  id?: string;
  /** GET /me/foto — usa a sessão em vez de `id`. */
  proprio?: boolean;
  /** Dica vinda da listagem (`Aluno.temFoto`, `ator_tem_foto`…): evita
   * tentar buscar foto para quem nunca teve uma. `undefined` = tenta assim
   * mesmo (caso de quem chama sem essa informação à mão). */
  temFoto?: boolean;
  tamanho?: number;
  className?: string;
  style?: React.CSSProperties;
  onClick?: () => void;
}

function useVisivelUmaVez<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [visivel, setVisivel] = useState(false);

  useEffect(() => {
    if (visivel) return;
    const alvo = ref.current;
    if (!alvo) return;
    // jsdom (Vitest) e navegadores muito antigos não têm IntersectionObserver
    // — nesse caso é mais seguro carregar direto do que nunca carregar.
    if (typeof IntersectionObserver === 'undefined') {
      setVisivel(true);
      return;
    }
    const observador = new IntersectionObserver(
      (entradas) => {
        if (entradas.some((e) => e.isIntersecting)) {
          setVisivel(true);
          observador.disconnect();
        }
      },
      { rootMargin: '200px' },
    );
    observador.observe(alvo);
    return () => observador.disconnect();
  }, [visivel]);

  return { ref, visivel };
}

export function Avatar({ tipo, nome, id, proprio = false, temFoto, tamanho, className, style, onClick }: Props) {
  const inicial = (nome || '?').trim().charAt(0).toUpperCase() || '?';
  const { ref, visivel } = useVisivelUmaVez<HTMLDivElement>();

  const { data } = useFotoPerfil({
    tipo, id, proprio,
    habilitada: visivel && temFoto !== false,
  });

  const estiloTamanho: React.CSSProperties = tamanho
    ? { width: tamanho, height: tamanho, fontSize: Math.round(tamanho * 0.42) }
    : {};

  return (
    <div ref={ref} className={className} style={{ ...estiloTamanho, ...style }} onClick={onClick}>
      {data?.fotoDataUrl ? (
        <img className="avatar__img" src={data.fotoDataUrl} alt={nome ? `Foto de ${nome}` : 'Foto de perfil'} />
      ) : (
        inicial
      )}
    </div>
  );
}
