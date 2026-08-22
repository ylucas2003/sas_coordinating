---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices". Também para revisar responsividade e comportamento em celular.
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Interface Guidelines

Revisa arquivos contra as Web Interface Guidelines da Vercel.

## Como funciona

1. Leia as regras de [regras.md](regras.md) — cópia versionada neste repositório
2. Leia os arquivos indicados (ou pergunte quais)
3. Cheque contra todas as regras
4. Reporte no formato `arquivo:linha`, terso e de alto sinal

## De onde vêm as regras

`regras.md` é cópia de
`https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md`,
baixada em 22/08/2026.

**Use a cópia local, não a rede.** O SKILL.md original manda buscar a URL a cada
review; foi trocado de propósito por duas razões: a revisão fica reprodutível
(mesma regra hoje e daqui a seis meses, e o diff das regras aparece no git), e
não depende de rede para rodar. Para atualizar, rebaixe o arquivo e commite o
diff — assim a mudança de régua é uma decisão visível, não um efeito colateral.

## Uso

Com argumento (arquivo ou padrão): leia as regras, leia os arquivos, aplique
tudo. Sem argumento: pergunte o que revisar.

As seções que mais pesam em celular são **Touch & Interaction**, **Safe Areas &
Layout**, **Forms** e **Performance** — ver [../../../docs/20-mobile.md](../../../docs/20-mobile.md).
