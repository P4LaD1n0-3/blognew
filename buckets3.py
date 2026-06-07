import os
import boto3
from botocore.exceptions import ClientError
from io import BytesIO

# --- 1. CONFIGURAÇÃO ---
# POR FAVOR, SUBSTITUA OS VALORES ABAIXO PELAS NOVAS CHAVES GERADAS NO BACKBLAZE
# Crie uma nova "Application Key" específica para o seu bucket "wesleyrolim-site".
B2_ACCESS_KEY_ID = '0058a00929f33850000000001'
B2_SECRET_ACCESS_KEY = 'K005GFKPN/PHQ5+DVEdNCDXhcEpOttU'

# Detalhes do seu bucket (estes estão corretos)
B2_ENDPOINT_URL = 'https://s3.us-east-005.backblazeb2.com'
B2_BUCKET_NAME = 'wesleyrolim-site'
B2_REGION_NAME = 'us-east-005' # Extraído do endpoint

# Verifica se as chaves foram atualizadas
if 'SUA_NOVA' in B2_ACCESS_KEY_ID or 'SUA_NOVA' in B2_SECRET_ACCESS_KEY:
    print("❌ ERRO: As chaves de acesso no script ainda são placeholders.")
    print("Por favor, gere uma nova Application Key no Backblaze e atualize as variáveis B2_ACCESS_KEY_ID e B2_SECRET_ACCESS_KEY.")
    exit()

print("--- Iniciando Teste de Conexão com o Bucket S3 (Backblaze B2) ---")

try:
    # --- 2. INICIALIZAÇÃO DO CLIENTE S3 ---
    # Criamos o cliente, especificando o endpoint do Backblaze.
    s3_client = boto3.client(
        's3',
        endpoint_url=B2_ENDPOINT_URL,
        aws_access_key_id=B2_ACCESS_KEY_ID,
        aws_secret_access_key=B2_SECRET_ACCESS_KEY,
        region_name=B2_REGION_NAME,
    )
    print("✅ Cliente S3 inicializado com sucesso.")

    # --- 3. TESTE DE CONEXÃO E PERMISSÕES ---
    # A maneira mais simples de testar é listar os objetos no bucket.
    # Se isso funcionar, suas chaves são válidas e têm permissão de leitura.
    print("\n--- Testando conexão e listando objetos... ---")
    s3_client.list_objects_v2(Bucket=B2_BUCKET_NAME, MaxKeys=1)
    print("✅ Conexão bem-sucedida! O bucket foi acessado com sucesso.")

    # --- 4. TESTE DE UPLOAD ---
    # Vamos criar um arquivo de teste em memória para fazer o upload.
    print("\n--- Testando upload de um arquivo... ---")
    file_content = b"Ola, Backblaze! A conexao a partir do script Python funcionou perfeitamente."
    file_object_key = "teste-de-conexao.txt"
    
    s3_client.upload_fileobj(
        BytesIO(file_content),       # O conteúdo do arquivo
        B2_BUCKET_NAME,              # O nome do bucket
        file_object_key              # O nome do arquivo no bucket
    )
    print(f"✅ Arquivo '{file_object_key}' enviado com sucesso para o bucket '{B2_BUCKET_NAME}'.")

    # --- 5. VALIDAÇÃO DO UPLOAD (GERANDO LINK TEMPORÁRIO) ---
    # Como seu bucket é privado, geramos uma URL pré-assinada para acessá-lo.
    print("\n--- Gerando link de acesso temporário para validação... ---")
    presigned_url = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': B2_BUCKET_NAME, 'Key': file_object_key},
        ExpiresIn=3600  # O link será válido por 1 hora
    )
    print("✅ Link temporário gerado! Copie e cole no seu navegador para verificar o arquivo:")
    print(f"\n   {presigned_url}\n")
    

except ClientError as e:
    # Captura erros comuns de autenticação ou permissão
    error_code = e.response.get("Error", {}).get("Code")
    if error_code == 'InvalidAccessKeyId':
        print("❌ ERRO DE AUTENTICAÇÃO: O Access Key ID fornecido não parece ser válido.")
    elif error_code == 'SignatureDoesNotMatch':
        print("❌ ERRO DE AUTENTICAÇÃO: A Secret Access Key fornecida está incorreta.")
    elif error_code == 'AccessDenied':
        print(f"❌ ERRO DE PERMISSÃO: As credenciais são válidas, mas não têm permissão para acessar o bucket '{B2_BUCKET_NAME}'.")
    else:
        print(f"❌ Ocorreu um erro inesperado do Boto3: {e}")

except Exception as e:
    print(f"❌ Ocorreu um erro geral no script: {e}")
