GEPUB — Pacote Educação (Round 1)

Conteúdo:
- apps/educacao/  (código Python do app)
- templates/educacao/ (templates do módulo)

Como aplicar (substituição segura):
1) Na raiz do projeto (onde está manage.py):

   cd ~/Desktop/gepub
   cp -r apps/educacao apps/educacao_backup_$(date +%Y%m%d_%H%M)
   cp -r templates/educacao templates/educacao_backup_$(date +%Y%m%d_%H%M) 2>/dev/null || true

2) Extraia este zip na raiz do projeto, preservando a estrutura:

   unzip -o educacao_round1.zip -d .

   (ele criará/atualizará: apps/educacao e templates/educacao)

3) Rode checks e migrações (se houver mudanças de models):

   python3 manage.py check
   python3 manage.py makemigrations educacao
   python3 manage.py migrate

4) Suba o servidor:

   python3 manage.py runserver

Testes rápidos recomendados:
- /educacao/ (dashboard)
- /educacao/turmas/ (lista/detalhe)
- /educacao/alunos/ (lista/detalhe)
- /educacao/matriculas/nova/
- /educacao/diarios/ -> /educacao/diario/<pk>/ -> Avaliações -> Lançar Notas
- /educacao/turmas/<pk>/horario/

Observações:
- Menu do módulo aponta “Avaliações/Notas” via Diário (evita NoReverseMatch por pk).
- Lançamento de notas usa campos do template: mat_<matricula_id>.
