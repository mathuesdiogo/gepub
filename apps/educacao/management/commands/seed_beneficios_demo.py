from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Cria dados demonstrativos completos do modulo Beneficios e Entregas (Educacao/Saude)."

    def add_arguments(self, parser):
        parser.add_argument("--slug", default="", help="Slug do municipio alvo. Se vazio, usa primeiro municipio ativo.")
        parser.add_argument("--password", default="12345678", help="Senha dos usuarios demo.")

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.accounts.models import Profile
        from apps.almoxarifado.models import AlmoxarifadoCadastro
        from apps.educacao.models import Aluno, Matricula, Turma
        from apps.educacao.models_beneficios import (
            BeneficioCampanha,
            BeneficioCampanhaAluno,
            BeneficioEdital,
            BeneficioEditalCriterio,
            BeneficioEditalDocumento,
            BeneficioEditalInscricao,
            BeneficioEditalInscricaoDocumento,
            BeneficioEditalRecurso,
            BeneficioEntrega,
            BeneficioEntregaItem,
            BeneficioRecorrenciaPlano,
            BeneficioTipo,
            BeneficioTipoItem,
        )
        from apps.educacao.services_beneficios import confirmar_entrega, estornar_entrega, gerar_ciclos_recorrencia
        from apps.org.models import Municipio, MunicipioModuloAtivo, Secretaria, SecretariaModuloAtivo, Unidade

        slug = (options.get("slug") or "").strip().lower()
        password = options.get("password") or "12345678"
        today = timezone.localdate()

        municipio = None
        if slug:
            municipio = Municipio.objects.filter(slug_site=slug, ativo=True).first()
            if not municipio:
                municipio = Municipio.objects.filter(nome__iexact=slug, ativo=True).first()
        if not municipio:
            municipio = Municipio.objects.filter(ativo=True).order_by("nome").first()
        if not municipio:
            raise CommandError("Nenhum municipio ativo encontrado para gerar seed demo.")

        self.stdout.write(self.style.WARNING(f"Gerando seed demo de Beneficios para {municipio.nome}/{municipio.uf}"))

        # Estrutura base
        sec_edu, _ = Secretaria.objects.get_or_create(
            municipio=municipio,
            nome="Secretaria Municipal de Educacao",
            defaults={"tipo_modelo": "educacao", "ativo": True},
        )
        sec_edu.ativo = True
        if hasattr(sec_edu, "tipo_modelo"):
            sec_edu.tipo_modelo = "educacao"
        sec_edu.save()

        sec_saude, _ = Secretaria.objects.get_or_create(
            municipio=municipio,
            nome="Secretaria Municipal de Saude",
            defaults={"tipo_modelo": "saude", "ativo": True},
        )
        sec_saude.ativo = True
        if hasattr(sec_saude, "tipo_modelo"):
            sec_saude.tipo_modelo = "saude"
        sec_saude.save()

        esc_a, _ = Unidade.objects.get_or_create(
            secretaria=sec_edu,
            nome="Escola Modelo Centro",
            defaults={"tipo": Unidade.Tipo.EDUCACAO, "ativo": True},
        )
        esc_a.tipo = Unidade.Tipo.EDUCACAO
        esc_a.ativo = True
        esc_a.save()

        esc_b, _ = Unidade.objects.get_or_create(
            secretaria=sec_edu,
            nome="Escola Modelo Bairro",
            defaults={"tipo": Unidade.Tipo.EDUCACAO, "ativo": True},
        )
        esc_b.tipo = Unidade.Tipo.EDUCACAO
        esc_b.ativo = True
        esc_b.save()

        ubs_a, _ = Unidade.objects.get_or_create(
            secretaria=sec_saude,
            nome="UBS Modelo Centro",
            defaults={"tipo": Unidade.Tipo.SAUDE, "ativo": True},
        )
        ubs_a.tipo = Unidade.Tipo.SAUDE
        ubs_a.ativo = True
        ubs_a.save()

        # Modulos ativos no catalogo
        for module in ("educacao", "almoxarifado", "saude", "comunicacao", "paineis"):
            MunicipioModuloAtivo.objects.update_or_create(
                municipio=municipio,
                modulo=module,
                defaults={"ativo": True},
            )
        for sec in (sec_edu, sec_saude):
            for module in ("educacao", "almoxarifado", "saude", "comunicacao"):
                SecretariaModuloAtivo.objects.update_or_create(
                    secretaria=sec,
                    modulo=module,
                    defaults={"ativo": True},
                )

        # Usuarios demonstrativos
        User = get_user_model()

        def ensure_user(username: str, full_name: str, email: str, role: str, secretaria=None, unidade=None):
            first, *rest = full_name.split(" ")
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": " ".join(rest),
                    "email": email,
                    "is_active": True,
                },
            )
            user.first_name = first
            user.last_name = " ".join(rest)
            user.email = email
            user.is_active = True
            user.set_password(password)
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.municipio = municipio
            profile.secretaria = secretaria
            profile.unidade = unidade
            profile.ativo = True
            profile.bloqueado = False
            profile.must_change_password = False
            profile.save()
            return user, created

        ensure_user(
            username=f"edu_semec_{municipio.id}",
            full_name="Gestor Educacao Demo",
            email=f"edu.semec{municipio.id}@demo.local",
            role=Profile.Role.EDU_SECRETARIO,
            secretaria=sec_edu,
        )
        ensure_user(
            username=f"edu_escola_{municipio.id}",
            full_name="Gestor Escola Demo",
            email=f"edu.escola{municipio.id}@demo.local",
            role=Profile.Role.EDU_DIRETOR,
            secretaria=sec_edu,
            unidade=esc_a,
        )
        ensure_user(
            username=f"sau_secret_{municipio.id}",
            full_name="Gestor Saude Demo",
            email=f"sau.secret{municipio.id}@demo.local",
            role=Profile.Role.SAU_SECRETARIO,
            secretaria=sec_saude,
        )

        # Turmas e alunos (20 alunos)
        turma_5a, _ = Turma.objects.get_or_create(unidade=esc_a, nome="5A Demo", ano_letivo=today.year)
        turma_eja, _ = Turma.objects.get_or_create(unidade=esc_b, nome="EJA Noite Demo", ano_letivo=today.year, defaults={"turno": Turma.Turno.NOITE})
        turma_5a.ativo = True
        turma_5a.save()
        turma_eja.ativo = True
        turma_eja.save()

        alunos = []
        for idx in range(1, 21):
            aluno_nome = f"Aluno Demo Beneficio {idx:02d}"
            aluno, _ = Aluno.objects.get_or_create(
                nome=aluno_nome,
                defaults={
                    "data_nascimento": today - timedelta(days=365 * (8 + (idx % 10))),
                    "nome_mae": f"Responsavel Demo {idx:02d}",
                    "telefone": f"55989999{idx:04d}",
                    "ativo": True,
                },
            )
            aluno.ativo = True
            if not aluno.telefone:
                aluno.telefone = f"55989999{idx:04d}"
            if not aluno.nome_mae:
                aluno.nome_mae = f"Responsavel Demo {idx:02d}"
            aluno.save()
            turma_ref = turma_5a if idx <= 12 else turma_eja
            Matricula.objects.get_or_create(
                aluno=aluno,
                turma=turma_ref,
                defaults={"situacao": Matricula.Situacao.ATIVA, "data_matricula": today},
            )
            alunos.append(aluno)

        # Itens de estoque
        estoque_data = [
            ("KIT-CAD-001", "Caderno 96 folhas", "UN", Decimal("120")),
            ("KIT-LAP-001", "Lapis grafite", "UN", Decimal("300")),
            ("KIT-BOR-001", "Borracha branca", "UN", Decimal("250")),
            ("KIT-MOC-001", "Mochila escolar", "UN", Decimal("80")),
            ("CESTA-ARZ-005", "Arroz 5kg", "UN", Decimal("90")),
            ("CESTA-FEJ-001", "Feijao 1kg", "UN", Decimal("120")),
            ("NEE-TAB-001", "Tablet acessibilidade", "UN", Decimal("20")),
            ("SAU-GLI-001", "Tiras glicemia caixa", "CX", Decimal("100")),
        ]
        estoque_items = {}
        for codigo, nome, unidade_medida, saldo in estoque_data:
            item, _ = AlmoxarifadoCadastro.objects.get_or_create(
                municipio=municipio,
                codigo=codigo,
                defaults={
                    "secretaria": sec_edu,
                    "unidade": esc_a,
                    "nome": nome,
                    "unidade_medida": unidade_medida,
                    "estoque_minimo": Decimal("10"),
                    "saldo_atual": saldo,
                    "valor_medio": Decimal("8.50"),
                    "status": AlmoxarifadoCadastro.Status.ATIVO,
                },
            )
            item.status = AlmoxarifadoCadastro.Status.ATIVO
            if item.saldo_atual < saldo:
                item.saldo_atual = saldo
            item.unidade_medida = unidade_medida
            item.secretaria = sec_saude if codigo.startswith("SAU-") else sec_edu
            item.unidade = ubs_a if codigo.startswith("SAU-") else esc_a
            item.save()
            estoque_items[codigo] = item

        # Tipos de beneficios + composicao
        beneficio_kit, _ = BeneficioTipo.objects.get_or_create(
            municipio=municipio,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Kit Escolar Infantil 2026",
            defaults={
                "secretaria": sec_edu,
                "categoria": BeneficioTipo.Categoria.KIT_ESCOLAR,
                "publico_alvo": BeneficioTipo.PublicoAlvo.FUNDAMENTAL,
                "periodicidade": BeneficioTipo.Periodicidade.ANUAL,
                "elegibilidade_json": {"etapa": "fundamental", "escolas": [esc_a.nome, esc_b.nome]},
                "exige_assinatura": True,
                "exige_foto": False,
                "exige_justificativa": False,
                "permite_segunda_via": True,
                "status": BeneficioTipo.Status.ATIVO,
            },
        )
        beneficio_kit.secretaria = sec_edu
        beneficio_kit.status = BeneficioTipo.Status.ATIVO
        beneficio_kit.save()

        beneficio_cesta, _ = BeneficioTipo.objects.get_or_create(
            municipio=municipio,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Cesta Basica EJA 2026",
            defaults={
                "secretaria": sec_edu,
                "categoria": BeneficioTipo.Categoria.CESTA_BASICA,
                "publico_alvo": BeneficioTipo.PublicoAlvo.EJA,
                "periodicidade": BeneficioTipo.Periodicidade.MENSAL,
                "elegibilidade_json": {"programa": "EJA", "renda_max": 1.5},
                "exige_assinatura": True,
                "exige_foto": True,
                "exige_justificativa": True,
                "permite_segunda_via": False,
                "status": BeneficioTipo.Status.ATIVO,
            },
        )
        beneficio_cesta.secretaria = sec_edu
        beneficio_cesta.status = BeneficioTipo.Status.ATIVO
        beneficio_cesta.save()

        beneficio_nee, _ = BeneficioTipo.objects.get_or_create(
            municipio=municipio,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Material NEE Acessibilidade 2026",
            defaults={
                "secretaria": sec_edu,
                "categoria": BeneficioTipo.Categoria.EQUIPAMENTO,
                "publico_alvo": BeneficioTipo.PublicoAlvo.NEE,
                "periodicidade": BeneficioTipo.Periodicidade.SOB_DEMANDA,
                "elegibilidade_json": {"nee": True, "laudo_obrigatorio": True},
                "exige_assinatura": True,
                "exige_foto": True,
                "exige_justificativa": True,
                "permite_segunda_via": False,
                "status": BeneficioTipo.Status.ATIVO,
            },
        )
        beneficio_nee.secretaria = sec_edu
        beneficio_nee.status = BeneficioTipo.Status.ATIVO
        beneficio_nee.save()

        beneficio_saude, _ = BeneficioTipo.objects.get_or_create(
            municipio=municipio,
            area=BeneficioTipo.Area.SAUDE,
            nome="Insumos Diabetes Programa 2026",
            defaults={
                "secretaria": sec_saude,
                "categoria": BeneficioTipo.Categoria.EQUIPAMENTO,
                "publico_alvo": BeneficioTipo.PublicoAlvo.PROGRAMAS,
                "periodicidade": BeneficioTipo.Periodicidade.MENSAL,
                "elegibilidade_json": {"programa_saude": "diabetes"},
                "exige_assinatura": True,
                "exige_foto": False,
                "exige_justificativa": False,
                "permite_segunda_via": True,
                "status": BeneficioTipo.Status.ATIVO,
            },
        )
        beneficio_saude.secretaria = sec_saude
        beneficio_saude.status = BeneficioTipo.Status.ATIVO
        beneficio_saude.save()

        def ensure_comp(beneficio, item_codigo, qtd, ordem, permite_sub=False, obs=""):
            item = estoque_items[item_codigo]
            comp, _ = BeneficioTipoItem.objects.get_or_create(
                beneficio=beneficio,
                item_estoque=item,
                defaults={
                    "quantidade": Decimal(str(qtd)),
                    "unidade": item.unidade_medida,
                    "permite_substituicao": permite_sub,
                    "observacao": obs,
                    "ordem": ordem,
                    "ativo": True,
                },
            )
            comp.quantidade = Decimal(str(qtd))
            comp.unidade = item.unidade_medida
            comp.permite_substituicao = permite_sub
            comp.observacao = obs
            comp.ordem = ordem
            comp.ativo = True
            comp.save()

        ensure_comp(beneficio_kit, "KIT-CAD-001", 1, 1)
        ensure_comp(beneficio_kit, "KIT-LAP-001", 2, 2)
        ensure_comp(beneficio_kit, "KIT-BOR-001", 1, 3)
        ensure_comp(beneficio_kit, "KIT-MOC-001", 1, 4, True, "Permite troca por bolsa escolar")
        ensure_comp(beneficio_cesta, "CESTA-ARZ-005", 1, 1)
        ensure_comp(beneficio_cesta, "CESTA-FEJ-001", 2, 2, True, "Pode substituir por macarrao")
        ensure_comp(beneficio_nee, "NEE-TAB-001", 1, 1, False, "Equipamento de tecnologia assistiva")
        ensure_comp(beneficio_saude, "SAU-GLI-001", 1, 1)

        # Campanha de distribuicao
        campanha, _ = BeneficioCampanha.objects.get_or_create(
            municipio=municipio,
            area=BeneficioTipo.Area.EDUCACAO,
            nome="Distribuicao Kit Escolar - Marco 2026 - Escola Modelo",
            defaults={
                "secretaria": sec_edu,
                "unidade": esc_a,
                "beneficio": beneficio_kit,
                "data_inicio": date(today.year, 3, 1),
                "data_fim": date(today.year, 3, 31),
                "quantidade_planejada": 15,
                "origem": BeneficioCampanha.Origem.ESTOQUE,
                "centro_custo": "EDU-MAT-2026",
                "referencia": "PROC-EDU-2026-001",
                "status": BeneficioCampanha.Status.EM_EXECUCAO,
            },
        )
        campanha.secretaria = sec_edu
        campanha.unidade = esc_a
        campanha.beneficio = beneficio_kit
        campanha.quantidade_planejada = 15
        campanha.status = BeneficioCampanha.Status.EM_EXECUCAO
        campanha.save()

        alunos_campanha = alunos[:15]
        for idx, aluno in enumerate(alunos_campanha, start=1):
            turma_ref = turma_5a if idx <= 10 else turma_eja
            item, _ = BeneficioCampanhaAluno.objects.get_or_create(
                campanha=campanha,
                aluno=aluno,
                defaults={
                    "turma": turma_ref,
                    "status": BeneficioCampanhaAluno.Status.SELECIONADO,
                },
            )
            if item.status not in {
                BeneficioCampanhaAluno.Status.ENTREGUE,
                BeneficioCampanhaAluno.Status.SELECIONADO,
            }:
                item.status = BeneficioCampanhaAluno.Status.SELECIONADO
                item.save(update_fields=["status"])

        # Entregas demonstrativas
        def ensure_entrega_for_aluno(aluno, marker: str, status_target: str):
            entrega = BeneficioEntrega.objects.filter(
                municipio=municipio,
                aluno=aluno,
                beneficio=beneficio_kit,
                campanha=campanha,
                observacao__icontains=marker,
            ).first()
            if not entrega:
                entrega = BeneficioEntrega.objects.create(
                    municipio=municipio,
                    secretaria=sec_edu,
                    unidade=esc_a,
                    area=BeneficioTipo.Area.EDUCACAO,
                    aluno=aluno,
                    campanha=campanha,
                    beneficio=beneficio_kit,
                    recebedor_tipo=BeneficioEntrega.RecebedorTipo.RESPONSAVEL,
                    recebedor_nome=aluno.nome_mae or f"Responsavel de {aluno.nome}",
                    recebedor_documento=f"RG-DEMO-{aluno.id:04d}",
                    recebedor_telefone=aluno.telefone,
                    assinatura_confirmada=True,
                    local_entrega=esc_a.nome,
                    observacao=f"{marker} - seed demonstrativo beneficios",
                    status=BeneficioEntrega.Status.PENDENTE,
                )
            if not entrega.itens.exists():
                for comp in beneficio_kit.itens.filter(ativo=True).order_by("ordem"):
                    qtd_ent = comp.quantidade
                    pendente = False
                    if marker == "ENTREGA_PARCIAL" and comp.ordem == 4:
                        qtd_ent = Decimal("0")
                        pendente = True
                    BeneficioEntregaItem.objects.create(
                        entrega=entrega,
                        composicao_item=comp,
                        item_estoque=comp.item_estoque,
                        item_nome=comp.item_nome,
                        quantidade_planejada=comp.quantidade,
                        quantidade_entregue=qtd_ent,
                        unidade=comp.unidade,
                        pendente=pendente,
                        substituido=False,
                    )
            if status_target == BeneficioEntrega.Status.ENTREGUE and entrega.status == BeneficioEntrega.Status.PENDENTE:
                try:
                    confirmar_entrega(entrega=entrega, user=entrega.responsavel_entrega)
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"Confirmacao ignorada para entrega #{entrega.pk}: {exc}"))
            if status_target == BeneficioEntrega.Status.ESTORNADO and entrega.status != BeneficioEntrega.Status.ESTORNADO:
                if entrega.status == BeneficioEntrega.Status.PENDENTE:
                    try:
                        confirmar_entrega(entrega=entrega, user=entrega.responsavel_entrega)
                    except Exception:
                        pass
                if entrega.status == BeneficioEntrega.Status.ENTREGUE:
                    try:
                        estornar_entrega(entrega=entrega, user=entrega.responsavel_entrega, motivo="Exemplo demonstrativo")
                    except Exception:
                        pass
            return entrega

        entregas_confirmadas = []
        for aluno in alunos_campanha[:5]:
            entregas_confirmadas.append(ensure_entrega_for_aluno(aluno, "ENTREGA_CONFIRMADA", BeneficioEntrega.Status.ENTREGUE))
        ensure_entrega_for_aluno(alunos_campanha[5], "ENTREGA_PARCIAL", BeneficioEntrega.Status.PENDENTE)
        ensure_entrega_for_aluno(alunos_campanha[6], "ENTREGA_ESTORNO", BeneficioEntrega.Status.ESTORNADO)

        # Edital e selecao
        edital, _ = BeneficioEdital.objects.get_or_create(
            municipio=municipio,
            numero_ano="01/2026-EJA",
            defaults={
                "secretaria": sec_edu,
                "area": BeneficioTipo.Area.EDUCACAO,
                "titulo": "Edital 01/2026 - Cesta Basica EJA",
                "beneficio": beneficio_cesta,
                "publico_alvo": BeneficioTipo.PublicoAlvo.EJA,
                "abrangencia": BeneficioEdital.Abrangencia.ESCOLAS,
                "inscricao_inicio": date(today.year, 2, 1),
                "inscricao_fim": date(today.year, 2, 20),
                "analise_inicio": date(today.year, 2, 21),
                "analise_fim": date(today.year, 2, 28),
                "resultado_preliminar_data": date(today.year, 3, 2),
                "prazo_recurso_data": date(today.year, 3, 5),
                "resultado_final_data": date(today.year, 3, 8),
                "texto": "Edital demonstrativo para distribuicao de cestas aos alunos EJA.",
                "status": BeneficioEdital.Status.RESULTADO_FINAL,
            },
        )
        edital.secretaria = sec_edu
        edital.beneficio = beneficio_cesta
        edital.status = BeneficioEdital.Status.RESULTADO_FINAL
        edital.save()
        edital.escolas.set([esc_b])

        criterios = [
            ("Matricula ativa no EJA", BeneficioEditalCriterio.Tipo.ELIMINATORIO, "cadastro_aluno", "turma CONTAINS EJA", 0, True, 1),
            ("Renda familiar ate 1.5 salario", BeneficioEditalCriterio.Tipo.PONTUACAO, "declaracao", "renda <= 1.5", 10, True, 2),
            ("Aluno NEE", BeneficioEditalCriterio.Tipo.PONTUACAO, "cadastro_aluno", "nee = true", 5, False, 3),
            ("Frequencia minima 75%", BeneficioEditalCriterio.Tipo.ELIMINATORIO, "historico", "frequencia >= 75", 0, False, 4),
        ]
        for nome, tipo, fonte, regra, peso, exige, ordem in criterios:
            crit, _ = BeneficioEditalCriterio.objects.get_or_create(
                edital=edital,
                nome=nome,
                defaults={
                    "tipo": tipo,
                    "fonte_dado": fonte,
                    "regra": regra,
                    "peso": peso,
                    "exige_comprovacao": exige,
                    "ordem": ordem,
                    "ativo": True,
                },
            )
            crit.tipo = tipo
            crit.fonte_dado = fonte
            crit.regra = regra
            crit.peso = peso
            crit.exige_comprovacao = exige
            crit.ordem = ordem
            crit.ativo = True
            crit.save()

        docs = [
            ("RG/CPF do responsavel", True, "pdf,jpg,png", date(today.year, 2, 20), False, 1),
            ("Comprovante de residencia", True, "pdf,jpg,png", date(today.year, 2, 20), False, 2),
            ("Declaracao de renda", True, "pdf,jpg,png", date(today.year, 2, 22), True, 3),
            ("Laudo NEE (quando aplicavel)", False, "pdf,jpg,png", date(today.year, 2, 25), False, 4),
        ]
        req_map = {}
        for nome, obrigatorio, fmt, prazo, permite_decl, ordem in docs:
            req, _ = BeneficioEditalDocumento.objects.get_or_create(
                edital=edital,
                nome=nome,
                defaults={
                    "obrigatorio": obrigatorio,
                    "formatos_aceitos": fmt,
                    "prazo_entrega": prazo,
                    "permite_declaracao": permite_decl,
                    "ordem": ordem,
                },
            )
            req.obrigatorio = obrigatorio
            req.formatos_aceitos = fmt
            req.prazo_entrega = prazo
            req.permite_declaracao = permite_decl
            req.ordem = ordem
            req.save()
            req_map[nome] = req

        inscricoes_status = [
            BeneficioEditalInscricao.Status.CLASSIFICADO,
            BeneficioEditalInscricao.Status.CLASSIFICADO,
            BeneficioEditalInscricao.Status.FINAL_DEFERIDO,
            BeneficioEditalInscricao.Status.FINAL_DEFERIDO,
            BeneficioEditalInscricao.Status.NAO_CLASSIFICADO,
            BeneficioEditalInscricao.Status.INAPTO,
            BeneficioEditalInscricao.Status.DOC_PENDENTE,
            BeneficioEditalInscricao.Status.RECURSO,
        ]
        for idx, status in enumerate(inscricoes_status, start=1):
            aluno = alunos[12 + (idx - 1)] if (12 + idx - 1) < len(alunos) else alunos[idx - 1]
            insc, _ = BeneficioEditalInscricao.objects.get_or_create(
                edital=edital,
                aluno=aluno,
                defaults={
                    "escola": esc_b,
                    "turma": turma_eja,
                    "dados_json": {"renda": float(1.0 + (idx * 0.1)), "dependentes": idx % 4, "origem": "escola"},
                    "status": status,
                    "pontuacao": Decimal(str(20 - idx)),
                },
            )
            insc.escola = esc_b
            insc.turma = turma_eja
            insc.status = status
            insc.pontuacao = Decimal(str(20 - idx))
            insc.atualizado_por = insc.criado_por
            insc.save()

            doc_seed_name = f"DOC-DEMO-{insc.pk}.txt"
            doc_content = f"Documento demonstrativo para inscricao {insc.pk}\n".encode("utf-8")
            for req in req_map.values():
                if not req.obrigatorio and idx % 2 == 0:
                    continue
                doc, created = BeneficioEditalInscricaoDocumento.objects.get_or_create(
                    inscricao=insc,
                    requisito=req,
                    defaults={"descricao": req.nome, "aprovado": True if status not in {BeneficioEditalInscricao.Status.DOC_PENDENTE} else None},
                )
                if created or not doc.arquivo:
                    from django.core.files.base import ContentFile

                    doc.arquivo.save(doc_seed_name, ContentFile(doc_content), save=False)
                if status == BeneficioEditalInscricao.Status.DOC_PENDENTE:
                    doc.aprovado = None
                    doc.observacao = "Pendente de validacao documental."
                else:
                    doc.aprovado = True
                    doc.observacao = "Documento validado na triagem."
                doc.save()

            if status == BeneficioEditalInscricao.Status.RECURSO:
                rec, _ = BeneficioEditalRecurso.objects.get_or_create(
                    inscricao=insc,
                    texto="Solicito revisao da pontuacao por comprovacao complementar.",
                    defaults={
                        "status": BeneficioEditalRecurso.Status.DEFERIDO,
                        "parecer": "Recurso deferido em seed demonstrativo.",
                    },
                )
                rec.status = BeneficioEditalRecurso.Status.DEFERIDO
                rec.parecer = "Recurso deferido em seed demonstrativo."
                rec.analisado_em = timezone.now()
                rec.save()

        # Recorrencias demonstrativas
        planos = []
        for aluno in alunos[:3]:
            plano, _ = BeneficioRecorrenciaPlano.objects.get_or_create(
                municipio=municipio,
                area=BeneficioTipo.Area.EDUCACAO,
                beneficio=beneficio_cesta,
                aluno=aluno,
                defaults={
                    "secretaria": sec_edu,
                    "unidade": esc_b,
                    "data_inicio": date(today.year, 3, 1),
                    "numero_ciclos": 3,
                    "frequencia": BeneficioRecorrenciaPlano.Frequencia.MENSAL,
                    "intervalo_dias": 30,
                    "geracao_automatica": True,
                    "permite_segunda_via": False,
                    "status": BeneficioRecorrenciaPlano.Status.ATIVA,
                    "observacao": "Plano demonstrativo de recorrencia mensal (3 ciclos).",
                },
            )
            plano.secretaria = sec_edu
            plano.unidade = esc_b
            plano.status = BeneficioRecorrenciaPlano.Status.ATIVA
            plano.geracao_automatica = True
            plano.save()
            gerar_ciclos_recorrencia(plano=plano)
            planos.append(plano)

        # Executa primeiro ciclo de um plano para demonstrar pipeline
        if planos:
            plano_exec = planos[0]
            primeiro_ciclo = plano_exec.ciclos.order_by("numero").first()
            if primeiro_ciclo and not primeiro_ciclo.entrega_id:
                entrega = BeneficioEntrega.objects.create(
                    municipio=municipio,
                    secretaria=plano_exec.secretaria,
                    unidade=plano_exec.unidade,
                    area=plano_exec.area,
                    aluno=plano_exec.aluno,
                    beneficio=plano_exec.beneficio,
                    plano_recorrencia=plano_exec,
                    ciclo_recorrencia=primeiro_ciclo,
                    data_hora=timezone.now(),
                    recebedor_tipo=BeneficioEntrega.RecebedorTipo.RESPONSAVEL,
                    recebedor_nome=plano_exec.aluno.nome_mae or f"Responsavel de {plano_exec.aluno.nome}",
                    assinatura_confirmada=True,
                    local_entrega=plano_exec.unidade.nome if plano_exec.unidade else "Ponto central",
                    observacao="Entrega gerada automaticamente por seed demo de recorrencia.",
                    status=BeneficioEntrega.Status.PENDENTE,
                )
                for comp in plano_exec.beneficio.itens.filter(ativo=True).order_by("ordem", "id"):
                    BeneficioEntregaItem.objects.create(
                        entrega=entrega,
                        composicao_item=comp,
                        item_estoque=comp.item_estoque,
                        item_nome=comp.item_nome,
                        quantidade_planejada=comp.quantidade,
                        quantidade_entregue=comp.quantidade,
                        unidade=comp.unidade or "UN",
                        pendente=False,
                        substituido=False,
                    )
                primeiro_ciclo.status = primeiro_ciclo.Status.SEPARADA
                primeiro_ciclo.entrega = entrega
                primeiro_ciclo.save(update_fields=["status", "entrega", "atualizado_em"])

        # Resumo final
        resumo = {
            "alunos_demo": Aluno.objects.filter(nome__startswith="Aluno Demo Beneficio ").count(),
            "tipos_beneficio": BeneficioTipo.objects.filter(municipio=municipio).count(),
            "itens_composicao": BeneficioTipoItem.objects.filter(beneficio__municipio=municipio).count(),
            "campanhas": BeneficioCampanha.objects.filter(municipio=municipio).count(),
            "campanha_alunos": BeneficioCampanhaAluno.objects.filter(campanha__municipio=municipio).count(),
            "entregas_total": BeneficioEntrega.objects.filter(municipio=municipio).count(),
            "entregas_confirmadas": BeneficioEntrega.objects.filter(municipio=municipio, status=BeneficioEntrega.Status.ENTREGUE).count(),
            "entregas_pendentes": BeneficioEntrega.objects.filter(municipio=municipio, status=BeneficioEntrega.Status.PENDENTE).count(),
            "entregas_estornadas": BeneficioEntrega.objects.filter(municipio=municipio, status=BeneficioEntrega.Status.ESTORNADO).count(),
            "editais": BeneficioEdital.objects.filter(municipio=municipio).count(),
            "inscricoes": BeneficioEditalInscricao.objects.filter(edital__municipio=municipio).count(),
            "recorrencias": BeneficioRecorrenciaPlano.objects.filter(municipio=municipio).count(),
        }
        self.stdout.write(self.style.SUCCESS("Seed demo de Beneficios concluido."))
        for k, v in resumo.items():
            self.stdout.write(f" - {k}: {v}")
