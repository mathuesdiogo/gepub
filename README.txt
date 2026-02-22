PATCH DEFINITIVO: Dashboard NEE (index) SAFE + template SUAP

Corrige:
- NoReverseMatch no /nee/ (não chama acompanhamento_list sem aluno_id)
- ImportError de index_simple (mantém index_simple como alias)
- Dashboard renderiza SEMPRE templates/nee/index.html e usa cards padronizados (link-card + section-grid)
- Se alguma URL ainda não existir no seu urls.py do NEE, o card não quebra o sistema (vira #)

Aplicar:
cd ~/Desktop/gepub
unzip -o ~/Downloads/nee_dashboard_definitivo_patch.zip -d .
python manage.py check
python manage.py runserver

Observação:
Este patch NÃO altera URLs nem cria helpers/decorators novos no seu projeto.
