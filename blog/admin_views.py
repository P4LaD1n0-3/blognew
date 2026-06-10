import json
import random
import re
import threading
import time
import urllib.parse

import requests
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views import View

from .models import Author, Category, Post


# =====================================================================
#  BOT 0: PESQUISA WEB — Raspa artigos reais para contexto (RAG)
# =====================================================================

class WebResearchBot:
    """Raspa artigos reais da web e extrai texto + imagens OG como contexto."""

    _UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def scrape_ddg_snippets(cls, query: str) -> list[str]:
        """Extrai snippets de texto do DuckDuckGo Lite (rápido, sem JS)."""
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                headers={"User-Agent": cls._UA},
                data={"q": query},
                timeout=10,
            )
            snippets = re.findall(
                r"<td class=['\"]result-snippet['\"]\s*>\s*(.*?)\s*</td>",
                resp.text,
                re.IGNORECASE | re.DOTALL,
            )
            clean = []
            for s in snippets:
                c = re.sub(r"<[^>]+>", "", s).strip()
                c = (c.replace("&#39;", "'")
                      .replace("&quot;", '"')
                      .replace("&amp;", "&")
                      .replace("&lt;", "<")
                      .replace("&gt;", ">"))
                if len(c) > 30:
                    clean.append(c)
            return clean[:6]
        except Exception as e:
            print(f"[WebResearch] Snippets erro: {e}")
            return []

    @classmethod
    def scrape_ddg_links(cls, query: str, max_links: int = 3) -> list[str]:
        """Obtém URLs reais de resultados do DuckDuckGo Lite."""
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                headers={"User-Agent": cls._UA},
                data={"q": query},
                timeout=10,
            )
            raw_urls = re.findall(r"uddg=([^&\"'\s]+)", resp.text)
            clean = []
            skip = {"youtube.com", "youtu.be", "duckduckgo.com", "bing.com", "google.com"}
            for u in raw_urls:
                decoded = urllib.parse.unquote(u)
                if decoded.startswith("http") and not any(s in decoded for s in skip):
                    clean.append(decoded)
            return clean[:max_links]
        except Exception as e:
            print(f"[WebResearch] Links erro: {e}")
            return []

    @classmethod
    def scrape_article(cls, url: str) -> dict | None:
        """Extrai og:image e parágrafos de texto de um artigo via regex."""
        try:
            resp = requests.get(url, headers={"User-Agent": cls._UA}, timeout=12)
            html = resp.text

            # og:image — tenta os dois formatos de atributo
            og = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                html, re.IGNORECASE,
            ) or re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.IGNORECASE,
            )
            image = og.group(1) if og else None

            # Parágrafos de texto (remove tags internas, filtra curtos)
            raw_paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
            paras = []
            for p in raw_paras:
                clean = re.sub(r"<[^>]+>", "", p).strip()
                clean = re.sub(r"\s+", " ", clean)
                if len(clean) > 100:
                    paras.append(clean)

            return {
                "url": url,
                "image": image,
                "text": "\n\n".join(paras[:6]),
            }
        except Exception as e:
            print(f"[WebResearch] Artigo erro {url[:50]}: {e}")
            return None

    @classmethod
    def collect_research(cls, topic: str) -> dict:
        """Orquestra a pesquisa: snippets DDG + conteúdo de 3 artigos reais."""
        result: dict = {"snippets": [], "og_images": [], "article_texts": []}
        try:
            result["snippets"] = cls.scrape_ddg_snippets(topic)
            links = cls.scrape_ddg_links(topic, max_links=3)
            for link in links:
                data = cls.scrape_article(link)
                if not data:
                    continue
                if data.get("image") and data["image"].startswith("http"):
                    result["og_images"].append(data["image"])
                if data.get("text"):
                    result["article_texts"].append(data["text"])
        except Exception as e:
            print(f"[WebResearch] collect_research erro: {e}")
        return result


# =====================================================================
#  MOTOR DE IMAGENS — DuckDuckGo Image Search (sem API key)
# =====================================================================

class ImageEngine:
    """Busca imagens reais na internet via DuckDuckGo."""

    _USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    @classmethod
    def search(cls, query: str, num: int = 5) -> list[dict]:
        """Retorna lista de dicts com url, title, width, height."""
        try:
            session = requests.Session()
            session.headers.update({"User-Agent": cls._USER_AGENT})

            token_resp = session.get(
                "https://duckduckgo.com/",
                params={"q": query, "t": "h_", "iax": "images", "ia": "images"},
                timeout=10,
            )
            vqd_match = (
                re.search(r'vqd="([^"]+)"', token_resp.text)
                or re.search(r"vqd='([^']+)'", token_resp.text)
                or re.search(r"vqd=([\d-]+)", token_resp.text)
            )
            if not vqd_match:
                return []

            img_resp = session.get(
                "https://duckduckgo.com/i.js",
                params={
                    "l": "us-en",
                    "o": "json",
                    "q": query,
                    "vqd": vqd_match.group(1),
                    "f": ",,,,,",
                    "p": "1",
                },
                headers={"Referer": "https://duckduckgo.com/"},
                timeout=10,
            )

            if img_resp.status_code != 200:
                return []

            results = []
            for r in img_resp.json().get("results", []):
                url = r.get("image", "")
                w, h = r.get("width", 0), r.get("height", 0)
                if url and w >= 400 and h >= 300:
                    results.append({"url": url, "title": r.get("title", ""), "width": w, "height": h})
                if len(results) >= num:
                    break
            return results

        except Exception as e:
            print(f"[ImageEngine] Erro: {e}")
            return []

    @classmethod
    def best_image_url(cls, query: str) -> str | None:
        results = cls.search(query, num=3)
        if results:
            results.sort(key=lambda r: r["width"] * r["height"], reverse=True)
            return results[0]["url"]
        return None

    @classmethod
    def download(cls, url: str) -> bytes | None:
        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": cls._USER_AGENT})
            if resp.status_code == 200 and len(resp.content) > 5000:
                return resp.content
        except Exception as e:
            print(f"[ImageEngine] Falha ao baixar {url[:60]}: {e}")
        return None


# =====================================================================
#  MOTOR DE IMAGENS — Pexels API (alta qualidade, chave configurada)
# =====================================================================

class PexelsEngine:
    """Busca fotos de alta qualidade no Pexels usando a API oficial."""

    @classmethod
    def search(cls, query: str) -> str | None:
        api_key = getattr(settings, "PEXELS_API_KEY", None)
        if not api_key:
            return None
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": api_key},
                params={"query": query, "per_page": 5, "orientation": "landscape"},
                timeout=10,
            )
            photos = resp.json().get("photos", [])
            if photos:
                # Escolhe aleatoriamente entre as 5 fotos para variar entre matérias
                src = random.choice(photos).get("src", {})
                return src.get("large2x") or src.get("large") or src.get("original")
        except Exception as e:
            print(f"[Pexels] Erro: {e}")
        return None


# =====================================================================
#  PIPELINE MULTI-AGENTE — 6 bots especializados
# =====================================================================

class AgentPipeline:
    """
    Pipeline de 6 bots para geração de matérias com qualidade editorial.

    Bot 0 (externo): WebResearchBot — raspa artigos reais e imagens OG
    Bot 1: Pesquisador — briefing fundamentado em dados reais
    Bot 2: Redator — artigo completo com fatos da pesquisa
    Bot 3: Editor Web — HTML semântico + SEO + marcadores de imagem
    Bot 4: Refinador de Queries — melhora as queries de imagem com contexto
    Bot 5: Curador de Imagens — OG > Pexels > DuckDuckGo
    """

    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self.logs: list[str] = []
        self.research_context: dict = {"snippets": [], "og_images": [], "article_texts": []}

    def _log(self, msg: str):
        print(msg)
        self.logs.append(msg)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        Extrai o primeiro objeto JSON válido de uma string.
        Usa contagem de chaves balanceadas para lidar com HTML aninhado
        no campo 'html', onde o regex greedy costuma falhar.
        """
        start = text.find("{")
        if start == -1:
            return {}
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate, strict=False)
                    except json.JSONDecodeError:
                        # Tenta escapar newlines dentro de strings e reparsa
                        try:
                            return json.loads(
                                re.sub(r'(?<!\\)\n', r'\\n', candidate), strict=False
                            )
                        except Exception:
                            return {}
        return {}

    def _call_llm(self, system: str, user: str, expect_json: bool = False) -> str | dict:
        """Chama a API Groq com retry automático em rate limits."""
        api_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        is_reasoning = "deepseek-r1" in self.model_name or "r1-distill" in self.model_name
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 1 if is_reasoning else 0.7,
        }

        for attempt in range(5):
            resp = requests.post(api_url, headers=headers, json=payload, timeout=180)

            if resp.status_code == 429:
                try:
                    err = resp.json().get("error", {}).get("message", "")
                    # Suporta: "in 8s", "in 1m8.888s", "in 1h5m0s"
                    m = re.search(r"in (?:(\d+)h)?(?:(\d+)m)?(\d+\.?\d*)s", err)
                    if m:
                        wait = (
                            int(m.group(1) or 0) * 3600
                            + int(m.group(2) or 0) * 60
                            + float(m.group(3))
                            + 3
                        )
                    else:
                        wait = 65
                except Exception:
                    wait = 65

                MAX_WAIT = 300  # 5 minutos — acima disso é quota esgotada
                if wait > MAX_WAIT:
                    raise Exception(
                        f"Quota de API esgotada. O Groq pede para aguardar "
                        f"{wait/60:.0f} minutos. Tente novamente mais tarde."
                    )
                self._log(f"[RATE LIMIT] Aguardando {wait:.0f}s (tentativa {attempt + 1}/5)...")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                try:
                    groq_msg = resp.json().get("error", {}).get("message", "") or resp.text[:400]
                except Exception:
                    groq_msg = resp.text[:400]
                raise Exception(f"Groq API {resp.status_code}: {groq_msg}")
            content = resp.json()["choices"][0]["message"]["content"]

            # Remove bloco de raciocínio interno dos modelos DeepSeek-R1 (<think>...</think>)
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            if expect_json:
                parsed = self._extract_json(content)
                if parsed:
                    return parsed
                # JSON inválido — aguarda e retenta em vez de desistir
                self._log(f"[AVISO] Resposta sem JSON válido (tentativa {attempt + 1}/5). Retentar...")
                time.sleep(10)
                continue
            return content

        raise Exception("Rate limit excedido após 5 tentativas. Aguarde 1 minuto.")

    # -----------------------------------------------------------------
    #  BOT 1: PESQUISADOR — Briefing com contexto web real
    # -----------------------------------------------------------------
    def agent_researcher(self, user_prompt: str, variation: int = 1, total: int = 1) -> str:
        self._log(f"\n📋 [BOT 1 PESQUISADOR] Elaborando briefing com dados reais...")

        # Monta bloco de contexto web se disponível
        web_block = ""
        snippets = self.research_context.get("snippets", [])
        article_texts = self.research_context.get("article_texts", [])

        if snippets or article_texts:
            parts = []
            if snippets:
                parts.append("SNIPPETS ENCONTRADOS NA WEB:\n" + "\n".join(f"• {s}" for s in snippets))
            if article_texts:
                combined = "\n\n---\n\n".join(article_texts[:2])
                parts.append(f"CONTEÚDO DE ARTIGOS REAIS:\n{combined[:3500]}")
            web_block = "\n\nCONTEXTO REAL PESQUISADO (use como base factual):\n" + "\n\n".join(parts)

        system = (
            "Você é um Pesquisador e Analista de Conteúdo sênior de uma redação digital.\n"
            "Sua tarefa é produzir um BRIEFING ESTRUTURADO que guiará o redator.\n\n"
            "O briefing DEVE conter:\n"
            "1. ÂNGULO EDITORIAL: Perspectiva única e relevante para abordar\n"
            "2. ESTRUTURA SUGERIDA: 4-6 seções/subtítulos recomendados\n"
            "3. DADOS-CHAVE: Fatos, estatísticas e contextos concretos a incluir\n"
            "4. TOM E ESTILO: Como o texto deve soar (investigativo, analítico, narrativo)\n"
            "5. PÚBLICO-ALVO: Para quem estamos escrevendo\n\n"
            "IMPORTANTE: Use os dados reais fornecidos como base. Não invente fatos.\n"
            "Retorne APENAS o briefing em texto puro. SEM HTML. SEM JSON."
        )

        variation_text = ""
        if total > 1:
            variation_text = (
                f"\n\n(Esta é a variação {variation} de {total}. "
                "Escolha um ÂNGULO EDITORIAL completamente diferente das outras variações, "
                "mas mantenha-se fiel aos fatos reais fornecidos.)"
            )

        return self._call_llm(system, f"TÓPICO: {user_prompt}{variation_text}{web_block}")

    # -----------------------------------------------------------------
    #  BOT 2: REDATOR — Artigo fundamentado em fatos reais
    # -----------------------------------------------------------------
    def agent_writer(self, briefing: str, user_prompt: str) -> str:
        self._log("✍️  [BOT 2 REDATOR] Redigindo artigo...")

        # Snippets como âncoras de fatos reais
        snippets = self.research_context.get("snippets", [])
        facts_block = ""
        if snippets:
            facts_block = (
                "\n\nFATOS REAIS DA PESQUISA (mencione ao menos 3 destes no artigo):\n"
                + "\n".join(f"• {s}" for s in snippets)
            )

        system = (
            "Você é um Jornalista Sênior premiado, com estilo envolvente e apurado.\n"
            "Receberá um BRIEFING da equipe de pesquisa, as instruções do editor "
            "e fatos reais coletados da web.\n\n"
            "REGRAS ABSOLUTAS:\n"
            "- Escreva um artigo LONGO (mínimo 800 palavras), rico em detalhes e narrativa.\n"
            "- Use os FATOS REAIS fornecidos — não invente estatísticas nem dados.\n"
            "- Use parágrafos bem construídos. Varie frases curtas de impacto com parágrafos analíticos.\n"
            "- Divida o texto em seções com títulos descritivos.\n"
            "- Inclua pelo menos uma citação ou frase memorável.\n"
            "- Tom profissional mas acessível — qualidade de revista.\n\n"
            "PROIBIDO:\n"
            "- NÃO use HTML, Markdown ou formatação especial.\n"
            "- NÃO retorne JSON.\n"
            "- NÃO invente fatos. Se um dado não estiver nas fontes, contextualize com honestidade.\n"
            "- Retorne APENAS o texto do artigo."
        )

        return self._call_llm(
            system,
            f"INSTRUÇÕES DO EDITOR: {user_prompt}\n\nBRIEFING DA PESQUISA:\n{briefing}{facts_block}",
        )

    # -----------------------------------------------------------------
    #  BOT 3: EDITOR WEB — HTML semântico + SEO + marcadores de imagem
    # -----------------------------------------------------------------
    def agent_editor(self, raw_text: str, user_prompt: str = "") -> dict:
        self._log("💻 [BOT 3 EDITOR WEB] Formatando HTML e SEO...")

        topic_line = (
            f"- TEMA DESTE ARTIGO: \"{user_prompt[:120]}\"\n"
            if user_prompt else ""
        )

        system = (
            "Você é um Editor Web e Especialista em SEO de uma publicação digital premium.\n"
            "Receberá um artigo em texto puro e deve transformá-lo em HTML semântico rico.\n\n"
            "REGRAS DE FORMATAÇÃO:\n"
            "- Use APENAS tags internas (sem <html>, <head>, <body>).\n"
            "- Subtítulos em <h2> com emojis sutis (ex: 🔍 Análise Detalhada).\n"
            "- Sub-subtítulos em <h3>.\n"
            "- Aplique <strong> nas palavras-chave e conceitos cruciais.\n"
            "- Citações em <blockquote style=\"border-left: 4px solid #10b981; "
            "padding: 15px 20px; font-style: italic; color: #555; margin: 25px 0; "
            "background: #f0fdf4; border-radius: 0 8px 8px 0;\">.\n"
            "- Listas com <ul> e <li> para enumerações.\n"
            "- Separadores <hr style=\"border:0; border-top: 1px solid #e5e7eb; margin: 35px 0;\"> "
            "entre grandes blocos.\n"
            "- Parágrafos em <p>.\n\n"
            f"MARCADORES DE IMAGEM:\n"
            f"{topic_line}"
            "- Insira exatamente 3 marcadores [IMG_HERE: descrição muito específica] "
            "entre parágrafos onde uma foto editorial enriqueceria a leitura.\n"
            "- A descrição DEVE referenciar explicitamente o tema do artigo com detalhes visuais únicos.\n"
            "- OBRIGATÓRIO: inclua o nome/produto/evento específico, nunca genérico.\n"
            "  Exemplo ERRADO: 'pessoa usando computador', 'grupo de pessoas'\n"
            "  Exemplo CERTO para CrossFire: '[IMG_HERE: CrossFire FPS game online battle arena gameplay]'\n"
            "  Exemplo CERTO para Origem série: '[IMG_HERE: Origen MGM series family road loop thriller scene]'\n"
            "- PROIBIDO usar: pessoa, pessoas, grupo, cena, ambiente, fundo, trabalhando, conceito\n\n"
            "RESPONDA em JSON VÁLIDO com estas chaves:\n"
            "{\n"
            '  "title": "Título magnético e cativante",\n'
            '  "meta_title": "Título SEO (máx 60 chars)",\n'
            '  "meta_description": "Descrição SEO atrativa (máx 160 chars)",\n'
            '  "html": "<todo o HTML com marcadores [IMG_HERE: ...]>",\n'
            '  "cover_search": "Termo ultra-específico para foto de capa (em inglês, inclua o nome do tema)",\n'
            '  "thoughts": "Breve log das decisões editoriais"\n'
            "}"
        )

        result = self._call_llm(system, f"ARTIGO PARA FORMATAR:\n\n{raw_text}", expect_json=True)

        if not result or "html" not in result:
            self._log("[FALLBACK] Editor falhou. Usando formatação de emergência.")
            lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]

            # Título: primeira linha não vazia com conteúdo real (não genérica)
            title = "Matéria Gerada por IA"
            for l in lines:
                if len(l) > 15 and not l.lower().startswith(("introdução", "introduction")):
                    title = l[:80]
                    break
            if title == "Matéria Gerada por IA" and lines:
                title = lines[0][:80]

            html_parts = []
            img_count = 0
            for idx, line in enumerate(lines):
                if not line:
                    continue
                if len(line) < 100 and line[0].isupper() and not line.endswith("."):
                    html_parts.append(f"<h2>{line}</h2>")
                    # Insere marcador de imagem após 1º, 3º e 5º subtítulo
                    if img_count < 3 and idx > 0:
                        topic_hint = line[:50]
                        html_parts.append(f"[IMG_HERE: {topic_hint} scene editorial photo]")
                        img_count += 1
                else:
                    html_parts.append(f"<p>{line}</p>")

            # Garante pelo menos 2 marcadores mesmo sem subtítulos
            existing = len(re.findall(r"\[IMG_HERE", "\n".join(html_parts)))
            paragraphs_idx = [i for i, p in enumerate(html_parts) if p.startswith("<p>")]
            for pi in paragraphs_idx:
                if existing >= 3:
                    break
                if pi > 0:
                    html_parts.insert(pi, f"[IMG_HERE: {title[:40]} thematic photo]")
                    existing += 1

            result = {
                "title": title,
                "meta_title": title[:60],
                "meta_description": title[:160],
                "html": "\n".join(html_parts),
                "cover_search": f"{title[:50]} dramatic scene",
                "thoughts": "Fallback de emergência com marcadores de imagem.",
            }

        return result

    # -----------------------------------------------------------------
    #  BOT 4: REFINADOR DE QUERIES — Melhora buscas de imagem com contexto
    # -----------------------------------------------------------------
    def agent_image_query_refiner(self, html: str, cover_search: str, user_prompt: str = "") -> dict:
        """
        Recebe o HTML formatado e refina as queries de imagem para serem
        mais específicas e em inglês (melhor resultado em bancos de fotos).
        """
        self._log("🔎 [BOT 4 REFINADOR] Otimizando queries de imagem...")

        # Extrai os marcadores atuais
        markers = re.findall(r"\[IMG_HERE:\s*(.*?)\]", html, re.IGNORECASE)
        if not markers and not cover_search:
            return {"cover_search": cover_search, "image_queries": []}

        markers_text = "\n".join(f"{i+1}. {m}" for i, m in enumerate(markers))

        topic_context = user_prompt[:150] if user_prompt else cover_search

        system = (
            f"Você é especialista em curadoria de imagens editoriais.\n"
            f"O artigo é ESPECIFICAMENTE sobre: \"{topic_context}\".\n\n"
            "REGRAS OBRIGATÓRIAS para cada query refinada:\n"
            f"1. A query DEVE conter o tema \"{cover_search[:60]}\" ou seu equivalente visual direto em inglês.\n"
            "2. Máximo 5 palavras, em inglês, otimizadas para Pexels.\n"
            "3. Especifique elementos visuais CONCRETOS do tema: objetos, ações, locais únicos.\n"
            "4. PROIBIDO usar: 'person', 'people', 'scene', 'background', 'concept' sozinhos.\n"
            "5. A capa deve ter impacto visual máximo e ser inequivocamente sobre o tema.\n\n"
            f"Exemplo para tema 'CrossFire game':\n"
            f"  Input: 'jogadores em batalha' → Output: 'CrossFire FPS esports tournament gameplay'\n"
            f"Exemplo para tema 'Origem série MGM':\n"
            f"  Input: 'família na estrada' → Output: 'Origen MGM thriller family trapped mystery'\n\n"
            "RESPONDA em JSON:\n"
            "{\n"
            '  "cover_search": "refined cover query in English (must include topic name)",\n'
            '  "image_queries": ["topic-specific query 1", "topic-specific query 2", "topic-specific query 3"]\n'
            "}"
        )

        user = (
            f"CAPA ATUAL: {cover_search}\n\n"
            f"MARCADORES DE IMAGEM:\n{markers_text}"
        )

        result = self._call_llm(system, user, expect_json=True)

        if not result or "cover_search" not in result:
            return {"cover_search": cover_search, "image_queries": markers}

        # Garante que temos queries suficientes
        refined_queries = result.get("image_queries", [])
        while len(refined_queries) < len(markers):
            refined_queries.append(markers[len(refined_queries)] if len(refined_queries) < len(markers) else cover_search)

        return {
            "cover_search": result["cover_search"],
            "image_queries": refined_queries,
        }

    # -----------------------------------------------------------------
    #  BOT 5: CURADOR DE IMAGENS — OG > Pexels > DuckDuckGo
    # -----------------------------------------------------------------
    def _get_best_image(self, query: str, og_candidates: list | None = None) -> str | None:
        """
        Busca a melhor imagem disponível em ordem de qualidade:
        1. og:image dos artigos raspados (garantidamente relevante ao tema)
        2. Pexels API (alta qualidade, chave disponível)
        3. DuckDuckGo Image Search (fallback)
        """
        # 1. OG images dos artigos reais (100% relevantes ao tópico)
        for url in (og_candidates or []):
            if url and url.startswith("http"):
                self._log(f"   🖼️ Usando OG image da pesquisa: {url[:70]}")
                return url

        # 2. Pexels (alta qualidade)
        url = PexelsEngine.search(query)
        if url:
            self._log(f"   ✅ Pexels: '{query[:40]}'")
            return url

        # 3. DuckDuckGo (fallback)
        url = ImageEngine.best_image_url(query)
        if url:
            self._log(f"   ✅ DDG: '{query[:40]}'")
            return url

        return None

    def agent_image_curator(
        self,
        html: str,
        cover_search: str,
        refined_queries: list | None = None,
    ) -> tuple[str, str | None]:
        """
        Processa [IMG_HERE: ...] usando queries refinadas e fontes priorizadas.
        Retorna (html_final, cover_url).
        """
        self._log("📸 [BOT 5 CURADOR DE IMAGENS] Buscando fotos reais...")

        og_images = self.research_context.get("og_images", [])
        og_pool = list(og_images)  # pool de imagens OG para consumir em ordem
        query_index = [0]  # índice para iterar queries refinadas

        def replace_image_marker(match):
            raw_desc = match.group(1).strip()

            # Usa query refinada se disponível, senão usa a original
            if refined_queries and query_index[0] < len(refined_queries):
                search_query = refined_queries[query_index[0]]
            else:
                search_query = raw_desc
            query_index[0] += 1

            self._log(f"   🔎 Imagem {query_index[0]}: '{search_query[:50]}'")

            # Seções usam Pexels → DDG (OG fica reservado para a capa)
            url = self._get_best_image(search_query)

            if url:
                return (
                    f'<figure style="margin: 30px 0; text-align: center;">'
                    f'<img src="{url}" alt="{raw_desc}" '
                    f'style="width:100%; max-height:500px; object-fit:cover; '
                    f'border-radius:12px; box-shadow: 0 4px 20px rgba(0,0,0,0.12);">'
                    f'<figcaption style="color:#888; font-size:0.85em; margin-top:8px; '
                    f'font-style:italic;">{raw_desc}</figcaption>'
                    f'</figure>'
                )
            self._log(f"   ⚠️ Sem imagem para: '{search_query[:50]}'")
            return ""

        final_html = re.sub(
            r"\[IMG_HERE:\s*(.*?)\]",
            replace_image_marker,
            html,
            flags=re.IGNORECASE,
        )
        # Compatibilidade com marcadores legados
        final_html = re.sub(
            r"\[BING_IMAGE:\s*(.*?)\]",
            replace_image_marker,
            final_html,
            flags=re.IGNORECASE,
        )

        # Capa: tenta OG do pool restante, depois Pexels, depois DDG
        self._log(f"   🖼️ Buscando capa: '{cover_search[:50]}'")
        cover_url = self._get_best_image(cover_search, og_candidates=og_pool or None)
        if cover_url:
            self._log("   ✅ Capa encontrada!")
        else:
            self._log("   ⚠️ Capa não encontrada.")

        return final_html, cover_url

    # -----------------------------------------------------------------
    #  ORQUESTRADOR — Executa o pipeline completo (6 bots)
    # -----------------------------------------------------------------
    def run(self, user_prompt: str, variation: int = 1, total: int = 1) -> dict:
        """Executa o pipeline completo e retorna o resultado."""
        self._log(f"\n{'='*60}")
        self._log(f"🚀 PIPELINE MULTI-AGENTE v2 — Matéria {variation}/{total}")
        self._log(f"   Modelo: {self.model_name}")
        self._log(f"   Prompt: {user_prompt[:80]}...")
        self._log(f"{'='*60}")

        # ── Bot 0: Pesquisa Web (RAG) ─────────────────────────────────
        self._log("\n🌐 [BOT 0 WEB RESEARCH] Raspando artigos reais da web...")
        self.research_context = WebResearchBot.collect_research(user_prompt)
        self._log(
            f"   Snippets: {len(self.research_context['snippets'])} | "
            f"OG Images: {len(self.research_context['og_images'])} | "
            f"Artigos: {len(self.research_context['article_texts'])}"
        )

        # ── Bot 1: Pesquisador ────────────────────────────────────────
        briefing = self.agent_researcher(user_prompt, variation, total)
        self._log(f"   📋 Briefing: {len(briefing)} chars")

        # ── Bot 2: Redator ────────────────────────────────────────────
        raw_article = self.agent_writer(briefing, user_prompt)
        self._log(f"   ✍️ Artigo: {len(raw_article)} chars (~{len(raw_article.split())} palavras)")

        # ── Bot 3: Editor Web ─────────────────────────────────────────
        editor_result = self.agent_editor(raw_article, user_prompt=user_prompt)
        self._log(f"   💻 HTML formatado | Título: {editor_result.get('title', 'N/A')}")

        # ── Bot 4: Refinador de Queries ───────────────────────────────
        refined = self.agent_image_query_refiner(
            editor_result.get("html", ""),
            editor_result.get("cover_search", user_prompt),
            user_prompt=user_prompt,
        )

        # ── Bot 5: Curador de Imagens ─────────────────────────────────
        final_html, cover_url = self.agent_image_curator(
            editor_result.get("html", ""),
            refined.get("cover_search", editor_result.get("cover_search", user_prompt)),
            refined_queries=refined.get("image_queries"),
        )

        # ── Keywords: extração automática para artigos relacionados ──
        self._log("🏷️ [KEYWORDS] Extraindo palavras-chave...")
        try:
            kw_system = (
                "Você extrai palavras-chave de artigos para uso em busca de artigos relacionados. "
                "Responda APENAS com JSON válido: {\"keywords\": [\"palavra1\", \"palavra2\", ...]}"
            )
            kw_user = (
                f"Tema: {user_prompt[:120]}\n"
                f"Título: {editor_result.get('title', '')}\n"
                f"Resumo: {editor_result.get('meta_description', '')}\n\n"
                "Extraia 6-10 palavras-chave em português, específicas ao tema. "
                "Inclua: nome do produto/série/evento, gênero, termos técnicos únicos."
            )
            kw_result = self._call_llm(kw_system, kw_user, expect_json=True)
            keywords_str = ", ".join(kw_result.get("keywords", []))
        except Exception:
            keywords_str = ""
        self._log(f"   🏷️ Keywords: {keywords_str[:80]}")

        self._log(f"\n✅ PIPELINE CONCLUÍDO — Matéria {variation}!")

        return {
            "title": editor_result.get("title", f"Matéria {variation}"),
            "meta_title": editor_result.get("meta_title", "")[:60],
            "meta_description": editor_result.get("meta_description", "")[:160],
            "html": final_html,
            "cover_url": cover_url,
            "keywords": keywords_str,
            "thoughts": editor_result.get("thoughts", ""),
            "logs": self.logs.copy(),
        }


# =====================================================================
#  VIEW DO DJANGO — IA Escritor
# =====================================================================

@method_decorator(staff_member_required, name="dispatch")
class AIWriterView(View):
    template_name = "admin/ai_writer.html"

    def get(self, request):
        context = {
            "categories": Category.objects.all(),
            "authors": Author.objects.filter(is_team_member=True),
            "saved_provider": request.session.get("ai_writer_provider", "groq_gpt_oss_120b"),
            "saved_api_key": request.session.get("ai_writer_api_key", ""),
            "saved_category": request.session.get("ai_writer_category", ""),
            "saved_author": request.session.get("ai_writer_author", ""),
            "saved_prompt": request.session.get("ai_writer_prompt", ""),
            "saved_quantity": request.session.get("ai_writer_quantity", 1),
            "saved_generate_image": request.session.get("ai_writer_generate_image", True),
            "saved_publish_now": request.session.get("ai_writer_publish_now", False),
        }
        context.update(admin.site.each_context(request))
        context["available_apps"] = admin.site.get_app_list(request)
        return render(request, self.template_name, context)

    def post(self, request):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        provider = request.POST.get("provider", "groq_gpt_oss_120b")
        api_key = request.POST.get("api_key")
        category_id = request.POST.get("category")
        author_id = request.POST.get("author")
        prompt = request.POST.get("prompt")
        quantity_str = request.POST.get("quantity", "1")
        quantity = max(1, min(10, int(quantity_str) if quantity_str.isdigit() else 1))
        current_iteration = int(request.POST.get("current_iteration", "1")) if is_ajax else 1

        generate_image = request.POST.get("generate_image") == "1"
        publish_now = request.POST.get("publish_now") == "1"

        if not is_ajax or current_iteration == 1:
            request.session["ai_writer_provider"] = provider
            request.session["ai_writer_api_key"] = api_key
            request.session["ai_writer_category"] = category_id
            request.session["ai_writer_author"] = author_id
            request.session["ai_writer_prompt"] = prompt
            request.session["ai_writer_quantity"] = quantity
            request.session["ai_writer_generate_image"] = generate_image
            request.session["ai_writer_publish_now"] = publish_now

        if not api_key or not prompt or not category_id or not author_id:
            messages.error(request, "Por favor, preencha todos os campos obrigatórios.")
            return redirect("custom_admin:ai_writer")

        try:
            category = Category.objects.get(id=category_id)
            author = Author.objects.get(id=author_id)

            if provider == "groq_gpt_oss_120b":
                model_name = "openai/gpt-oss-120b"
            else:
                model_name = "llama-3.3-70b-versatile"

            success_count = 0
            loop_range = [current_iteration - 1] if is_ajax else range(quantity)

            for i in loop_range:
                try:
                    pipeline = AgentPipeline(model_name, api_key)
                    result = pipeline.run(prompt, variation=i + 1, total=quantity)

                    post = Post()
                    post.title = result["title"]
                    post.content = result["html"]
                    post.category = category
                    post.author = author
                    post.status = "published" if publish_now else "draft"
                    post.meta_title = result["meta_title"]
                    post.meta_description = result["meta_description"]
                    post.keywords = result.get("keywords", "")

                    if generate_image and result.get("cover_url"):
                        try:
                            img_bytes = ImageEngine.download(result["cover_url"])
                            if img_bytes:
                                fname = f"{slugify(result['title'])[:30]}_cover.jpg"
                                post.thumbnail.save(fname, ContentFile(img_bytes), save=False)
                        except Exception as e:
                            print(f"[AVISO] Erro ao salvar capa: {e}")
                            messages.warning(request, f"Matéria salva, mas erro na capa: {e}")

                    post.save()
                    auto_translate_post(post)
                    success_count += 1

                    if is_ajax:
                        return JsonResponse({
                            "status": "success",
                            "title": result["title"],
                            "thoughts": result["thoughts"],
                            "logs": result["logs"],
                        })

                except requests.exceptions.RequestException as e:
                    details = ""
                    if hasattr(e, "response") and e.response is not None:
                        details = f" — {e.response.text[:300]}"
                    msg = f"Erro de API na matéria {i+1}: {e}{details}"
                    print(f"\n[ERRO] {msg}\n")
                    if is_ajax:
                        return JsonResponse({"status": "error", "error": msg})
                    messages.warning(request, msg)

                except Exception as e:
                    msg = f"Erro na matéria {i+1}: {e}"
                    print(f"\n[ERRO FATAL] {msg}\n")
                    if is_ajax:
                        return JsonResponse({"status": "error", "error": msg})
                    messages.warning(request, msg)

            if success_count > 0:
                messages.success(request, f"{success_count} matéria(s) gerada(s) com sucesso!")
                if "ai_writer_prompt" in request.session:
                    del request.session["ai_writer_prompt"]
                return redirect(reverse("custom_admin:blog_post_changelist"))
            else:
                messages.error(request, "Nenhuma matéria pôde ser gerada. Veja os alertas.")
                return redirect("custom_admin:ai_writer")

        except Exception as e:
            messages.error(request, f"Erro inesperado: {e}")
            return redirect("custom_admin:ai_writer")


# =====================================================================
#  BOT DE TRADUÇÃO AUTOMÁTICA — Groq + HTML-safe
# =====================================================================

class TranslationBot:
    """
    Traduz posts para EN, ES e FR preservando toda a estrutura HTML.
    Usa llama-3.3-70b (rápido, gratuito, bom para tradução).
    """

    _LANGUAGES = {"en": "English", "es": "Spanish", "fr": "French"}
    _MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str):
        self.api_key = api_key

    # ------------------------------------------------------------------
    def _call(self, system: str, user: str, timeout: int = 120) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        for attempt in range(4):
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            if resp.status_code == 429:
                try:
                    err = resp.json().get("error", {}).get("message", "")
                    m = re.search(r"in (?:(\d+)h)?(?:(\d+)m)?(\d+\.?\d*)s", err)
                    wait = (
                        int(m.group(1) or 0) * 3600
                        + int(m.group(2) or 0) * 60
                        + float(m.group(3))
                        + 3
                    ) if m else 65
                except Exception:
                    wait = 65
                if wait > 300:
                    raise Exception(f"Quota de API esgotada para tradução ({wait/60:.0f} min).")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        raise Exception("Rate limit de tradução excedido após 4 tentativas.")

    # ------------------------------------------------------------------
    def _translate_fields(self, title: str, meta_title: str, meta_desc: str, lang_code: str) -> dict:
        """Traduz campos de texto simples em uma única chamada (JSON)."""
        lang = self._LANGUAGES[lang_code]
        system = (
            f"Translate from Brazilian Portuguese to {lang}. "
            "Return a JSON object with exactly these keys: title, meta_title, meta_description. "
            "Return ONLY valid JSON, no markdown, no code blocks, no extra text."
        )
        user = json.dumps(
            {"title": title, "meta_title": meta_title, "meta_description": meta_desc},
            ensure_ascii=False,
        )
        raw = self._call(system, user)
        return AgentPipeline._extract_json(raw)

    # ------------------------------------------------------------------
    def _translate_html(self, html: str, lang_code: str) -> str:
        """Traduz HTML preservando todas as tags, atributos e media."""
        lang = self._LANGUAGES[lang_code]
        system = (
            f"Translate the following HTML from Brazilian Portuguese to {lang}.\n"
            "STRICT RULES:\n"
            "1. Translate ONLY the visible text between HTML tags.\n"
            "2. Keep ALL HTML tags and attributes (src, href, class, id, style, data-*) EXACTLY unchanged.\n"
            "3. Keep ALL image and media URLs unchanged.\n"
            "4. You MAY translate alt=\"\" values.\n"
            "5. Return ONLY the translated HTML — no markdown, no code blocks, no extra text."
        )
        # Limita o HTML para evitar estouro de tokens
        return self._call(system, html[:14000], timeout=150)

    # ------------------------------------------------------------------
    def translate_post(self, post) -> None:
        """Traduz um Post para EN, ES e FR, salvando diretamente na tabela de traduções."""
        from parler.models import TranslationDoesNotExist

        post.set_current_language("pt-br")
        src_title = post.title or ""
        src_meta_title = post.meta_title or ""
        src_meta_desc = post.meta_description or ""
        src_html = post.content or ""

        for lang_code in self._LANGUAGES:
            try:
                text = self._translate_fields(src_title, src_meta_title, src_meta_desc, lang_code)
                translated_html = self._translate_html(src_html, lang_code)

                title = (text.get("title") or "").strip() or src_title
                meta_title = (text.get("meta_title") or "")[:60]
                meta_desc = (text.get("meta_description") or "")[:160]
                slug = slugify(title)[:200] or f"post-{post.pk}-{lang_code}"

                # Recusa salvar se o HTML traduzido for menor que 20% do original
                # (sinal de que a tradução falhou ou foi truncada)
                min_len = max(50, len(src_html) * 0.20)
                if len(translated_html.strip()) < min_len:
                    print(
                        f"[TranslationBot] ⚠️ {lang_code}: conteúdo suspeito "
                        f"({len(translated_html)} chars vs {len(src_html)} original). "
                        "Tradução ignorada para não sobrescrever com conteúdo vazio."
                    )
                    continue

                try:
                    trans = post.get_translation(lang_code)
                    trans.title = title
                    trans.slug = slug
                    trans.content = translated_html
                    trans.meta_title = meta_title
                    trans.meta_description = meta_desc
                    trans.save()
                except TranslationDoesNotExist:
                    post.create_translation(
                        lang_code,
                        title=title,
                        slug=slug,
                        content=translated_html,
                        meta_title=meta_title,
                        meta_description=meta_desc,
                    )

                print(f"[TranslationBot] ✅ {lang_code}: '{title}'")

            except Exception as exc:
                print(f"[TranslationBot] ❌ {lang_code}: {exc}")


# =====================================================================
#  VIEW: CONFIGURAÇÕES DE IA
# =====================================================================

@method_decorator(staff_member_required, name="dispatch")
class AISettingsView(View):
    template_name = "admin/ai_settings.html"

    def get(self, request):
        from .models import SiteSettings
        site_cfg = SiteSettings.load()
        api_key = site_cfg.groq_api_key or ""
        masked = ("•" * (len(api_key) - 4) + api_key[-4:]) if len(api_key) > 4 else ("•" * len(api_key))
        context = {
            "groq_api_key": api_key,
            "masked_key": masked,
            "has_key": bool(api_key),
        }
        context.update(admin.site.each_context(request))
        context["available_apps"] = admin.site.get_app_list(request)
        return render(request, self.template_name, context)

    def post(self, request):
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        action = request.POST.get("action", "")

        if action == "test_connection":
            api_key = request.POST.get("api_key", "").strip()
            if not api_key:
                return JsonResponse({"status": "error", "error": "Insira uma chave API primeiro."})
            try:
                pipeline = AgentPipeline("llama-3.3-70b-versatile", api_key)
                result = pipeline._call_llm(
                    "Você é um assistente de teste. Responda APENAS com a palavra: CONECTADO",
                    "ping",
                    expect_json=False,
                )
                snippet = str(result).strip()[:80]
                return JsonResponse({"status": "success", "message": f"Conexão estabelecida! Resposta: {snippet}"})
            except Exception as exc:
                return JsonResponse({"status": "error", "error": str(exc)[:300]})

        if action == "save_key":
            from .models import SiteSettings
            api_key = request.POST.get("api_key", "").strip()
            from django.db import connection as db_conn
            # Update only the groq_api_key column to avoid translatable-model complexity
            SiteSettings.objects.filter(pk=1).update(groq_api_key=api_key)
            verb = "salva" if api_key else "removida"
            messages.success(request, f"Chave API Groq {verb} com sucesso! Os botões de IA nos posts agora funcionarão.")
            return redirect(reverse("custom_admin:ai_settings"))

        messages.error(request, "Ação inválida.")
        return redirect(reverse("custom_admin:ai_settings"))


def auto_translate_post(post) -> None:
    """
    Verifica se há chave API configurada nas SiteSettings e, se houver,
    dispara a tradução em uma thread de fundo (não bloqueia a resposta HTTP).
    """
    from .models import SiteSettings

    try:
        api_key = SiteSettings.load().groq_api_key or ""
    except Exception:
        api_key = ""

    if not api_key:
        return

    def _run():
        try:
            TranslationBot(api_key).translate_post(post)
        except Exception as exc:
            print(f"[auto_translate_post] Erro geral: {exc}")

    threading.Thread(target=_run, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────
#  8 ESTILOS VISUAIS ÚNICOS para "Formatar Conteúdo"
# ─────────────────────────────────────────────────────────────────────
_FORMAT_THEMES = [
    {
        "name": "Minimalista Elegante",
        "h2":  "border:none; background:transparent; font-family:'Inter', sans-serif; color:#111827; padding:0; padding-bottom:12px; border-bottom:2px solid #e5e7eb; margin:48px 0 24px; font-size:2em; font-weight:800; letter-spacing:-0.02em; line-height:1.2;",
        "h3":  "border:none; background:transparent; font-family:'Inter', sans-serif; color:#374151; padding:0; margin:32px 0 16px; font-size:1.5em; font-weight:700; letter-spacing:-0.01em;",
        "strong": "color:#111827; font-weight:700; background:rgba(243,244,246,0.8); padding:0 4px; border-radius:4px;",
        "blockquote": "border:none; border-left:4px solid #111827; background:#f9fafb; padding:24px 32px; border-radius:0 12px 12px 0; margin:40px 0; font-style:italic; color:#4b5563; font-size:1.15em; line-height:1.7;",
        "hr": "border:0; border-top:1px solid #e5e7eb; margin:48px 0;",
        "table": "width:100%; border-collapse:collapse; margin:32px 0; font-family:'Inter', sans-serif; font-size:0.95em; border-radius:8px; overflow:hidden; border:1px solid #e5e7eb;",
        "th": "background:#f9fafb; color:#111827; padding:16px; text-align:left; font-weight:600; border-bottom:1px solid #e5e7eb;",
        "td": "padding:16px; border-bottom:1px solid #f3f4f6; color:#4b5563;",
    },
    {
        "name": "Neon Tech (Dark Mode Vibe)",
        "h2":  "border:none; background:linear-gradient(90deg, #10b981, #3b82f6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-family:'Roboto', sans-serif; padding:0; margin:48px 0 24px; font-size:2.2em; font-weight:900; letter-spacing:0.5px;",
        "h3":  "border:none; background:transparent; font-family:'Roboto', sans-serif; color:#3b82f6; padding:0; border-left:4px solid #10b981; padding-left:16px; margin:32px 0 16px; font-size:1.6em; font-weight:700;",
        "strong": "color:#10b981; font-weight:800;",
        "blockquote": "border:none; border-left:4px solid #3b82f6; background:rgba(59,130,246,0.05); padding:24px 32px; border-radius:8px; margin:40px 0; font-style:italic; color:#1e293b; font-size:1.1em; box-shadow:inset 4px 0 0 #3b82f6;",
        "hr": "border:0; height:2px; background:linear-gradient(90deg, transparent, #10b981, #3b82f6, transparent); margin:48px 0;",
        "table": "width:100%; border-collapse:collapse; margin:32px 0; font-family:'Roboto', sans-serif; font-size:0.95em; border-radius:12px; overflow:hidden; box-shadow:0 10px 15px -3px rgba(0,0,0,0.1);",
        "th": "background:#0f172a; color:#f8fafc; padding:16px; text-align:left; font-weight:600;",
        "td": "padding:16px; border-bottom:1px solid #e2e8f0; color:#334155; background:#f8fafc;",
    },
    {
        "name": "Revista Clássica",
        "h2":  "border:none; background:transparent; font-family:'Playfair Display', serif; color:#7f1d1d; padding:0; text-align:center; margin:56px 0 28px; font-size:2.4em; font-style:italic; font-weight:700; position:relative;",
        "h3":  "border:none; background:transparent; font-family:'Montserrat', sans-serif; color:#991b1b; padding:0; text-transform:uppercase; letter-spacing:2px; margin:40px 0 16px; font-size:1.1em; font-weight:800; border-bottom:1px solid #fecaca; padding-bottom:8px;",
        "strong": "color:#7f1d1d; font-weight:700; font-family:'Montserrat', sans-serif;",
        "blockquote": "border:none; border-top:3px solid #7f1d1d; border-bottom:3px solid #7f1d1d; background:transparent; padding:32px 0; margin:48px auto; font-style:italic; color:#450a0a; font-family:'Playfair Display', serif; font-size:1.4em; text-align:center; max-width:80%; line-height:1.6;",
        "hr": "border:0; border-top:1px solid #fca5a5; margin:48px 0; display:flex; justify-content:center; align-items:center;",
        "table": "width:100%; border-collapse:collapse; margin:32px 0; font-family:'Montserrat', sans-serif; font-size:0.9em;",
        "th": "background:#fff; color:#7f1d1d; padding:16px; text-align:center; font-weight:800; text-transform:uppercase; border-top:2px solid #7f1d1d; border-bottom:2px solid #7f1d1d;",
        "td": "padding:16px; border-bottom:1px solid #fee2e2; color:#450a0a; text-align:center;",
    },
    {
        "name": "Coral Glassmorphism",
        "h2":  "border:none; background:rgba(254,226,226,0.5); backdrop-filter:blur(8px); border-radius:12px; font-family:'Outfit', sans-serif; color:#be123c; padding:16px 24px; margin:48px 0 24px; font-size:1.8em; font-weight:800; box-shadow:0 4px 6px rgba(225,29,72,0.05);",
        "h3":  "border:none; background:transparent; font-family:'Outfit', sans-serif; color:#e11d48; padding:0; margin:32px 0 16px; font-size:1.4em; font-weight:700; display:inline-block; border-bottom:3px solid #fecdd3;",
        "strong": "color:#e11d48; font-weight:800;",
        "blockquote": "border:none; border-left:5px solid #f43f5e; background:linear-gradient(90deg, rgba(254,226,226,0.4) 0%, transparent 100%); padding:24px 32px; border-radius:12px; margin:40px 0; font-style:italic; color:#881337; font-size:1.15em;",
        "hr": "border:0; height:3px; background:#fecdd3; border-radius:3px; margin:48px 0; width:50%;",
        "table": "width:100%; border-collapse:separate; border-spacing:0; margin:32px 0; font-family:'Outfit', sans-serif; font-size:0.95em; border:1px solid #fecdd3; border-radius:16px; overflow:hidden;",
        "th": "background:rgba(254,226,226,0.6); color:#be123c; padding:16px; text-align:left; font-weight:700;",
        "td": "padding:16px; border-bottom:1px solid #fff1f2; color:#4c0519;",
    },
    {
        "name": "Ocean Deep",
        "h2":  "border:none; background:transparent; font-family:'Poppins', sans-serif; color:#0f766e; padding:0; border-left:8px solid #0d9488; padding-left:20px; margin:48px 0 24px; font-size:2.1em; font-weight:800; line-height:1.2;",
        "h3":  "border:none; background:#f0fdfa; font-family:'Poppins', sans-serif; color:#115e59; padding:12px 20px; border-radius:8px; margin:32px 0 16px; font-size:1.4em; font-weight:600;",
        "strong": "color:#0d9488; font-weight:700; border-bottom:2px solid #99f6e4;",
        "blockquote": "border:none; border-left:none; background:#115e59; padding:32px; border-radius:16px; margin:40px 0; font-style:italic; color:#ccfbf1; font-size:1.2em; box-shadow:0 10px 25px -5px rgba(13,148,136,0.4); text-align:center;",
        "hr": "border:0; height:1px; background:linear-gradient(90deg, transparent, #0d9488, transparent); margin:48px 0;",
        "table": "width:100%; border-collapse:collapse; margin:32px 0; font-family:'Poppins', sans-serif; font-size:0.95em;",
        "th": "background:#0d9488; color:#fff; padding:16px; text-align:left; font-weight:600; border-radius:8px 8px 0 0;",
        "td": "padding:16px; border-bottom:1px solid #ccfbf1; color:#134e4a; background:#f0fdfa;",
    },
    {
        "name": "Ouro Real (Premium)",
        "h2":  "border:none; background:linear-gradient(135deg, #b45309 0%, #f59e0b 50%, #b45309 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-family:'Cinzel', serif; padding:0; text-align:center; margin:56px 0 28px; font-size:2.5em; font-weight:700; letter-spacing:1px;",
        "h3":  "border:none; background:transparent; font-family:'Lora', serif; color:#b45309; padding:0; margin:32px 0 16px; font-size:1.5em; font-weight:600; font-style:italic; text-align:center;",
        "strong": "color:#b45309; font-weight:700;",
        "blockquote": "border:none; border-top:1px solid #fcd34d; border-bottom:1px solid #fcd34d; background:rgba(254,243,199,0.3); padding:24px 32px; margin:40px 0; font-style:italic; color:#78350f; font-size:1.2em; font-family:'Lora', serif; text-align:center;",
        "hr": "border:0; height:1px; background:#f59e0b; margin:48px 0; position:relative; overflow:visible; display:flex; justify-content:center; align-items:center;",
        "table": "width:100%; border-collapse:collapse; margin:32px 0; font-family:'Lora', serif; font-size:1em; border-top:2px solid #b45309; border-bottom:2px solid #b45309;",
        "th": "background:transparent; color:#92400e; padding:16px; text-align:left; font-weight:700; border-bottom:1px solid #fcd34d;",
        "td": "padding:16px; border-bottom:1px dashed #fde68a; color:#78350f;",
    },
    {
        "name": "Cyberpunk Amarelo",
        "h2":  "border:none; background:#eab308; color:#000; font-family:'Space Grotesk', sans-serif; padding:12px 24px; margin:48px 0 24px; font-size:2em; font-weight:900; text-transform:uppercase; letter-spacing:2px; clip-path:polygon(0 0, 100% 0, 95% 100%, 0 100%); display:inline-block;",
        "h3":  "border:none; background:transparent; font-family:'Space Grotesk', sans-serif; color:#ca8a04; padding:0; margin:32px 0 16px; font-size:1.4em; font-weight:700; text-transform:uppercase; border-left:4px solid #eab308; padding-left:16px;",
        "strong": "background:#eab308; color:#000; font-weight:800; padding:2px 6px;",
        "blockquote": "border:none; border-left:8px solid #ca8a04; background:#fef08a; padding:24px 32px; margin:40px 0; font-style:normal; font-weight:600; color:#000; font-size:1.15em; font-family:'Space Grotesk', sans-serif;",
        "hr": "border:0; border-top:4px dotted #eab308; margin:48px 0;",
        "table": "width:100%; border-collapse:collapse; margin:32px 0; font-family:'Space Grotesk', sans-serif; font-size:0.95em; border:2px solid #000;",
        "th": "background:#000; color:#eab308; padding:16px; text-align:left; font-weight:700; text-transform:uppercase;",
        "td": "padding:16px; border-bottom:1px solid #000; color:#000; background:#fff;",
    },
    {
        "name": "Lavanda Suave",
        "h2":  "border:none; background:transparent; font-family:'Nunito', sans-serif; color:#6b21a8; padding:0; margin:48px 0 24px; font-size:2em; font-weight:800; border-bottom:3px dashed #d8b4fe; padding-bottom:12px;",
        "h3":  "border:none; background:rgba(216,180,254,0.3); font-family:'Nunito', sans-serif; color:#7e22ce; padding:8px 16px; border-radius:50px; margin:32px 0 16px; font-size:1.4em; font-weight:700; display:inline-block;",
        "strong": "color:#6b21a8; font-weight:800;",
        "blockquote": "border:none; border-left:4px solid #a855f7; background:#faf5ff; padding:24px 32px; border-radius:16px; margin:40px 0; font-style:italic; color:#581c87; font-size:1.15em; box-shadow:0 4px 15px rgba(168,85,247,0.1);",
        "hr": "border:0; height:4px; background:#e9d5ff; border-radius:4px; margin:48px 0;",
        "table": "width:100%; border-collapse:separate; border-spacing:0; margin:32px 0; font-family:'Nunito', sans-serif; font-size:0.95em; border-radius:12px; overflow:hidden; box-shadow:0 4px 6px rgba(0,0,0,0.05);",
        "th": "background:#e9d5ff; color:#581c87; padding:16px; text-align:left; font-weight:700;",
        "td": "padding:16px; border-bottom:1px solid #f3e8ff; color:#4c1d95; background:#fff;",
    }
]


# =====================================================================
#  NOVA VIEW: FORMATAR CONTEÚDO com IA  (estilo único a cada clique)
# =====================================================================

_FORMAT_P_STYLE  = "line-height:1.85; color:#374151; margin-bottom:18px; font-size:1.05em;"
_FORMAT_UL_STYLE = "line-height:1.9; color:#374151; margin:16px 0 16px 24px;"
_FORMAT_LI_STYLE = "margin-bottom:8px;"

# Mini-exemplo fixo: mostra PROMOÇÃO de <p> curto para <h2>/<h3> + estilização
_MINI_EXAMPLE_IN = (
    '<p>Seção Principal</p>'
    '<p>Texto do parágrafo com conteúdo mais longo descrevendo algo importante.</p>'
    '<p>1. Subseção Numerada</p>'
    '<p>Detalhe da subseção aqui.</p>'
    '<strong>palavra chave</strong>'
)

# Modelos menores que precisam de prompt simplificado (instruction-following fraco)
_SMALL_MODELS = frozenset({
    "llama-3.1-8b-instant", "gemma2-9b-it",
    "openai/gpt-oss-20b", "groq/compound-mini",
    "meta-llama/llama-4-scout-17b-16e-instruct",
})


def _is_small_model(model_name: str) -> bool:
    if model_name in _SMALL_MODELS:
        return True
    n = model_name.lower()
    return any(f"{d}b" in n for d in ["7", "8", "9", "13", "17"])


def _truncate_html_safe(html: str, max_chars: int = 13000) -> str:
    """Trunca no fechamento de uma tag, sem cortar dentro de um atributo."""
    if len(html) <= max_chars:
        return html
    cutoff = html.rfind(">", 0, max_chars)
    return html[: cutoff + 1] if cutoff > max_chars // 2 else html[:max_chars]


def _mini_example_out(theme: dict) -> str:
    """Saída esperada do exemplo: demonstra promoção de <p> curto para <h2>/<h3>."""
    return (
        f'<h2 style="{theme["h2"]}">Seção Principal</h2>'
        f'<p style="{_FORMAT_P_STYLE}">Texto do parágrafo com conteúdo mais longo descrevendo algo importante.</p>'
        f'<h3 style="{theme["h3"]}">1. Subseção Numerada</h3>'
        f'<p style="{_FORMAT_P_STYLE}">Detalhe da subseção aqui.</p>'
        f'<strong style="{theme["strong"]}">palavra chave</strong>'
    )


def _detect_and_promote_headings(html: str) -> str:
    """
    Heurística para artigos escritos como texto plano (apenas <p>).
    Promove <p> curtos sem pontuação final a <h2> ou <h3>.

    Regras:
    - texto ≤ 120 chars E não termina com . ! ? , ; → candidato a heading
    - começa com dígito+ponto/parêntese (1. / 2) / etc.) → <h3>
    - caso contrário → <h2>
    """
    _MAX = 120
    _NO_END = ".!?,;"

    def maybe_promote(m: re.Match) -> str:
        inner = m.group(1)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        if not text or len(text) < 4 or len(text) > _MAX:
            return m.group(0)
        if text[-1] in _NO_END:
            return m.group(0)
        tag = "h3" if re.match(r"^\d+[\.\)]\s", text) else "h2"
        return f"<{tag}>{inner}</{tag}>"

    return re.sub(r"<p>(.*?)</p>", maybe_promote, html, flags=re.DOTALL)


def _apply_styles_regex(html: str, theme: dict) -> str:
    """
    Fallback 100% confiável: promove headings e aplica os estilos do tema via regex.
    Nunca falha, nunca perde conteúdo.
    """
    # Pré-processamento: promove <p> que parecem títulos de seção
    html = _detect_and_promote_headings(html)

    style_map = [
        ("p",          _FORMAT_P_STYLE),
        ("h2",         theme["h2"]),
        ("h3",         theme["h3"]),
        ("strong",     theme["strong"]),
        ("em",         "font-style:italic;"),
        ("blockquote", theme["blockquote"]),
        ("ul",         _FORMAT_UL_STYLE),
        ("ol",         _FORMAT_UL_STYLE),
        ("li",         _FORMAT_LI_STYLE),
        ("table",      theme.get("table", "")),
        ("th",         theme.get("th", "")),
        ("td",         theme.get("td", "")),
    ]

    def make_replacer(tag: str, style: str):
        def replacer(m: re.Match) -> str:
            attrs = m.group(1) or ""
            # Remove estilo existente para não duplicar
            attrs = re.sub(r'\s*style\s*=\s*(["\'])[^"\']*\1', "", attrs)
            attrs = attrs.strip()
            base = f"<{tag} style=\"{style}\""
            return f"{base} {attrs}>" if attrs else f"{base}>"
        return replacer

    for tag, style in style_map:
        pattern = re.compile(rf"<{tag}(\s[^>]*)?>", re.IGNORECASE)
        html = pattern.sub(make_replacer(tag, style), html)

    # <hr> é auto-fechante — trata separadamente
    html = re.sub(
        r"<hr[^>]*/?>",
        f'<hr style="{theme["hr"]}">',
        html, flags=re.IGNORECASE,
    )
    return html


_REASONING_PHRASES = re.compile(
    r"I need to apply|the original HTML|the provided HTML|Let me start by|"
    r"Okay,?\s+I need|I'll apply the|I will apply|I should apply|"
    r"Let me think|the user(?:'s)? instructions|apply the styles to|"
    r"applying the styles|step by step\.",
    re.IGNORECASE,
)


def _clean_html_output(raw: str) -> str:
    """
    Remove artefatos de modelos ao redor do HTML.
    Retorna string vazia se o conteúdo parecer raciocínio inline em vez de HTML.
    """
    if not raw or not isinstance(raw, str):
        return ""

    # 1. Remove blocos <think> (DeepSeek / Qwen / modelos explícitos de raciocínio)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # Tenta extrair de um bloco markdown primeiro!
    match = re.search(r"```(?:html|xml)?\s*\n(.*?)\n\s*```", raw, re.DOTALL | re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
    else:
        # 2. Remove code fences soltos nas pontas
        raw = re.sub(r"^```[^\n]*\n?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"\n?```[^\n]*$", "", raw, flags=re.IGNORECASE).strip()

        # 3. Localiza o início real do HTML: primeira tag de bloco com style=
        first_styled = re.search(
            r"<(?:p|h[1-6]|div|ul|ol|li|strong|em|blockquote|figure|table|hr|span)\s[^>]*style\s*=",
            raw, re.IGNORECASE,
        )
        if first_styled:
            # Se a tag estilizada aparece mais de 200 chars adiante, é raciocínio antes do HTML
            if first_styled.start() > 200:
                return ""
            raw = raw[first_styled.start():]
        else:
            # Sem style= nenhum → tenta qualquer tag de bloco bem no início (primeiros 10%)
            first_block = re.search(
                r"<(?:p|h[1-6]|div|ul|ol|blockquote|figure|table)\b",
                raw, re.IGNORECASE,
            )
            if first_block and first_block.start() < max(100, len(raw) // 10):
                raw = raw[first_block.start():]
            else:
                return ""

    # 4. Trim após o último fechamento de tag
    last_gt = raw.rfind(">")
    if 0 <= last_gt < len(raw) - 1:
        raw = raw[: last_gt + 1]

    return raw.strip()


def _is_valid_format_result(result: str, original: str) -> bool:
    """
    Critérios de aceitação do HTML formatado pelo LLM:
    1. Começa com uma tag HTML real
    2. Contém style= (prova que estilos foram aplicados)
    3. Tem tamanho razoável (≥ 60% do original; estilos SOMAM, não removem)
    4. Preservou os elementos de bloco (p + h1-h6 + li); promoção p→h é válida
    5. Não contém frases típicas de raciocínio LLM inline
    """
    if not result:
        return False
    if not re.match(r"\s*<[a-zA-Z]", result):
        return False
    if "style=" not in result:
        return False
    if len(result) < len(original) * 0.6:
        return False
    # Conta elementos de bloco; promoção p→h é legítima e não conta como perda
    _block = r"<(?:p|h[1-6]|li)[\s>]"
    orig_blocks = len(re.findall(_block, original, re.IGNORECASE))
    res_blocks  = len(re.findall(_block, result,   re.IGNORECASE))
    if orig_blocks > 2 and res_blocks < orig_blocks * 0.6:
        return False
    # Detecta raciocínio inline: extrai texto puro e procura frases de LLM
    text_only = re.sub(r"<[^>]+>", " ", result)
    if _REASONING_PHRASES.search(text_only):
        return False
    return True


def _build_format_prompt_full(theme: dict) -> str:
    """Prompt para modelos grandes (≥ 30 B) — português, com exemplo concreto."""
    return (
        "Você é um processador de HTML editorial. Recebe HTML de um artigo e devolve "
        "o mesmo HTML com inline styles e estrutura semântica melhorada.\n\n"
        f"TEMA: {theme['name']}\n\n"
        "PASSO 1 — PROMOVER TÍTULOS (faça ANTES de estilizar):\n"
        "• Se um <p> tem texto curto (até 120 chars) SEM ponto/vírgula/exclamação no final\n"
        "  → promova para <h2> (seção) ou <h3> (subseção numerada como '1. Texto')\n"
        "• Parágrafos longos (> 120 chars) ou com pontuação final → mantém como <p>\n\n"
        "PASSO 2 — APLICAR ESTILOS em TODOS os elementos (inclusive os promovidos):\n"
        f'  <p>          →  style="{_FORMAT_P_STYLE}"\n'
        f'  <h2>         →  style="{theme["h2"]}"\n'
        f'  <h3>         →  style="{theme["h3"]}"\n'
        f'  <strong>     →  style="{theme["strong"]}"\n'
        f'  <blockquote> →  style="{theme["blockquote"]}"\n'
        f'  <hr>         →  style="{theme["hr"]}"\n'
        f'  <ul>         →  style="{_FORMAT_UL_STYLE}"\n'
        f'  <ol>         →  style="{_FORMAT_UL_STYLE}"\n'
        f'  <li>         →  style="{_FORMAT_LI_STYLE}"\n\n'
        "REGRAS INVIOLÁVEIS:\n"
        "• Preserva TODO o texto — apenas muda tags e adiciona style=\n"
        "• Preserva imagens, links, figuras, src, href exatamente como estão\n"
        "• RESPONDA EXCLUSIVAMENTE COM UM BLOCO MARKDOWN ````html ... ```` CONTENDO O HTML.\n\n"
        f"EXEMPLO (entrada → saída esperada):\n"
        f"ENTRADA: {_MINI_EXAMPLE_IN}\n"
        f"SAÍDA:\n```html\n{_mini_example_out(theme)}\n```\n\n"
        "Processe o HTML recebido agora e retorne apenas o bloco ```html."
    )


def _build_format_prompt_simple(theme: dict) -> str:
    """Prompt ultra-direto para modelos pequenos (≤ 20 B)."""
    return (
        "HTML formatter. Two steps:\n\n"
        "STEP 1 - PROMOTE HEADINGS:\n"
        "• Short <p> (≤120 chars, no period/comma/exclamation at end) → convert to <h2> or <h3>\n"
        "• <p> starting with '1. ' '2. ' etc → <h3>. Others → <h2>.\n"
        "• Long <p> or ending with . ! ? , ; → keep as <p>\n\n"
        "STEP 2 - ADD STYLES to ALL elements:\n"
        f'p → style="{_FORMAT_P_STYLE}"\n'
        f'h2 → style="{theme["h2"]}"\n'
        f'h3 → style="{theme["h3"]}"\n'
        f'strong → style="{theme["strong"]}"\n'
        f'blockquote → style="{theme["blockquote"]}"\n'
        f'hr → style="{theme["hr"]}"\n'
        f'ul, ol → style="{_FORMAT_UL_STYLE}"\n'
        f'li → style="{_FORMAT_LI_STYLE}"\n\n'
        "Keep ALL text. Output ONLY a markdown block: ```html ... ```\n\n"
        f"Example input: {_MINI_EXAMPLE_IN}\n"
        f"Example output:\n```html\n{_mini_example_out(theme)}\n```"
    )


@method_decorator(staff_member_required, name="dispatch")
class FormatContentView(View):
    """
    Recebe HTML do TinyMCE e devolve HTML com inline styles aplicados.
    Garante que o conteúdo NUNCA é perdido: se o LLM falhar, aplica
    estilos via regex Python puro como fallback de segurança.
    """

    def post(self, request):
        from .models import SiteSettings
        try:
            api_key = request.POST.get("api_key") or SiteSettings.load().groq_api_key or ""
        except Exception:
            api_key = ""

        if not api_key:
            return JsonResponse({
                "status": "error",
                "error": "Configure a Chave API Groq em Configurações do Site primeiro.",
            })

        html_content = request.POST.get("content", "").strip()
        if not html_content:
            return JsonResponse({"status": "error", "error": "O conteúdo está vazio."})

        # Remove estilos embutidos existentes para garantir que o LLM não mantenha o layout antigo
        html_clean = re.sub(r'\sstyle\s*=\s*(["\']).*?\1', '', html_content, flags=re.IGNORECASE)

        theme = random.choice(_FORMAT_THEMES)
        model_name = request.POST.get("model", "llama-3.3-70b-versatile")
        small = _is_small_model(model_name)

        # Prompt primário e alternativo (invertidos por tamanho de modelo)
        prompts = (
            [_build_format_prompt_simple(theme), _build_format_prompt_full(theme)]
            if small
            else [_build_format_prompt_full(theme), _build_format_prompt_simple(theme)]
        )

        html_to_send = _truncate_html_safe(html_clean)
        user_msg = f"HTML DO ARTIGO:\n\n{html_to_send}"

        try:
            pipeline = AgentPipeline(model_name, api_key)
            result_html = None  # será preenchido pelo LLM ou pelo fallback

            for attempt, system_prompt in enumerate(prompts):
                raw = pipeline._call_llm(system_prompt, user_msg, expect_json=False)
                cleaned = _clean_html_output(str(raw))

                if cleaned and _is_valid_format_result(cleaned, html_content):
                    result_html = cleaned
                    break

                pipeline._log(
                    f"[FORMAT] Tentativa {attempt + 1} inválida "
                    f"(len={len(cleaned) if cleaned else 0}, style={'style=' in cleaned if cleaned else False}). "
                    "Retentar..."
                )

            # ── Fallback Python puro ──────────────────────────────────────────
            # Se ambas as tentativas com LLM falharam, aplica estilos via regex.
            # O conteúdo é SEMPRE preservado; apenas o LLM pode perder conteúdo.
            if result_html is None:
                pipeline._log("[FORMAT] LLM falhou nas 2 tentativas. Usando fallback regex.")
                result_html = _apply_styles_regex(html_content, theme)

            return JsonResponse({
                "status": "success",
                "html": result_html,
                "theme": theme["name"],
            })

        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)})


# =====================================================================
#  NOVA VIEW: TRADUZIR POST ON-DEMAND com IA
# =====================================================================

@method_decorator(staff_member_required, name="dispatch")
class TranslatePostView(View):
    """Dispara tradução EN/ES/FR para um post existente via botão no admin."""

    def post(self, request):
        from .models import Post, SiteSettings
        try:
            api_key = SiteSettings.load().groq_api_key or ""
        except Exception:
            api_key = ""

        if not api_key:
            return JsonResponse({
                "status": "error",
                "error": "Configure a Chave API Groq em Configurações do Site primeiro.",
            })

        post_id = request.POST.get("post_id", "").strip()
        if not post_id:
            return JsonResponse({
                "status": "error",
                "error": "Salve o post primeiro para poder traduzir.",
            })

        try:
            post = Post.objects.get(pk=post_id)
        except Post.DoesNotExist:
            return JsonResponse({"status": "error", "error": "Post não encontrado."})

        def _run():
            try:
                TranslationBot(api_key).translate_post(post)
            except Exception as exc:
                print(f"[TranslatePostView] Erro: {exc}")

        threading.Thread(target=_run, daemon=True).start()

        return JsonResponse({
            "status": "started",
            "message": "Tradução iniciada em segundo plano! Aguarde 1–3 minutos e recarregue a página para ver o resultado.",
        })


# =====================================================================
#  NOVA VIEW: GERAR SEO + SLUG com IA
# =====================================================================

@method_decorator(staff_member_required, name="dispatch")
class GenerateSEOView(View):
    """Gera meta_title, meta_description e keywords baseados no conteúdo do post."""

    def post(self, request):
        from .models import SiteSettings
        try:
            api_key = SiteSettings.load().groq_api_key or ""
        except Exception:
            api_key = ""

        if not api_key:
            return JsonResponse({
                "status": "error",
                "error": "Configure a Chave API Groq em Configurações do Site primeiro.",
            })

        title = request.POST.get("title", "").strip()
        content = request.POST.get("content", "").strip()

        if not title and not content:
            return JsonResponse({
                "status": "error",
                "error": "Preencha o título ou o conteúdo antes de gerar o SEO.",
            })

        try:
            clean_content = re.sub(r"<[^>]+>", " ", content)
            clean_content = re.sub(r"\s+", " ", clean_content).strip()[:3000]

            pipeline = AgentPipeline("llama-3.3-70b-versatile", api_key)

            system = (
                "Você é um especialista em SEO para blogs em português brasileiro.\n"
                "Analise o título e o conteúdo e gere os metadados SEO ideais.\n\n"
                "REGRAS:\n"
                "- meta_title: título SEO atrativo em português, máx 60 chars\n"
                "- meta_description: descrição SEO completa e atrativa em português, máx 155 chars\n"
                "- keywords: 8-12 palavras-chave específicas ao tema, separadas por vírgula, em português\n\n"
                'RESPONDA em JSON com exatamente estas chaves: '
                '{"meta_title":"","meta_description":"","keywords":""}'
            )

            user = f"TÍTULO: {title}\n\nCONTEÚDO:\n{clean_content}"
            result = pipeline._call_llm(system, user, expect_json=True)

            if not result or not isinstance(result, dict):
                return JsonResponse({
                    "status": "error",
                    "error": "IA não retornou resultado válido. Tente novamente.",
                })

            return JsonResponse({
                "status": "success",
                "meta_title": (result.get("meta_title") or "")[:60],
                "meta_description": (result.get("meta_description") or "")[:160],
                "keywords": result.get("keywords", ""),
            })

        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)})
