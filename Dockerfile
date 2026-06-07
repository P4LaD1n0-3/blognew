# ----------------------------------------------------------------
# Estágio 1: Configuração do Ambiente e Instalação de Dependências
# ----------------------------------------------------------------
# Usando uma imagem base oficial do Python.
FROM python:3.10

# Define variáveis de ambiente essenciais para o ambiente Python em contêineres.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Define o diretório de trabalho dentro do contêiner.
# Todos os comandos a seguir serão executados a partir de /app.
WORKDIR /app

# Copia o arquivo de dependências primeiro e as instala.
# Isso aproveita o cache do Docker: se o requirements.txt não mudar,
# o Docker não reinstala tudo a cada novo build, acelerando o processo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------------------
# Estágio 2: Cópia do Código e Preparação da Aplicação
# ----------------------------------------------------------------
# Agora, copia todo o resto do código do seu projeto para o contêiner.
COPY . .

# --- CRIAÇÃO DOS DIRETÓRIOS ---
# Cria os diretórios que serão usados para dados persistentes e estáticos.
RUN mkdir -p /app/staticfiles
RUN mkdir -p /app/media
RUN mkdir -p /app/data

# --- DEFINIÇÃO DE VOLUMES ---
# Declara ao Docker que estas pastas são "pontos de montagem" para volumes.
# Isso permite que o Easypanel conecte volumes persistentes a elas corretamente.
# A linha 'VOLUME /app/staticfiles' foi REMOVIDA. Arquivos estáticos fazem
# parte do build da aplicação e não devem ser montados em um volume externo,
# pois isso esconderia os arquivos coletados pelo 'collectstatic'.
VOLUME /app/media
VOLUME /app/data

# --- BUILD DO TAILWIND CSS ---
# Baixa o Tailwind CLI standalone (linux/x64) e gera o CSS otimizado a partir dos templates.
RUN curl -sL https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
      -o /tmp/tailwindcss \
    && chmod +x /tmp/tailwindcss \
    && /tmp/tailwindcss -i tailwind.input.css -o blog/static/assets/css/tailwind.css --minify \
    && rm /tmp/tailwindcss

# --- BUILD STEPS FINAIS ---
# Executa a coleta de arquivos estáticos para que o WhiteNoise possa servi-los.
# Esta etapa agora funcionará corretamente, pois a pasta não será sobreposta por um volume.
RUN python manage.py collectstatic --noinput

# Expõe a porta que o Gunicorn usará dentro do contêiner.
# A porta 7221 precisa ser mapeada no Easypanel.
EXPOSE 7220

# Define uma DATABASE_URL padrão para SQLite.
# Lembre-se: a variável que você define no painel do Easypanel (com o PostgreSQL)
# irá SOBRESCREVER esta. Isso aqui é só um fallback.
ENV DATABASE_URL=sqlite:////app/data/db.sqlite3

# Comando final para iniciar o servidor Gunicorn quando o contêiner rodar.
CMD ["gunicorn", "--bind", "0.0.0.0:7220", "core.wsgi:application"]
