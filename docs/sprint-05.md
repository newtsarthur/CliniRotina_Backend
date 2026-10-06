# Sprint 05 — Material técnico para o documento

> Rascunho com o conteúdo técnico **real** do código. Capa (grupo, turma,
> integrantes), capturas de tela e a seção de dificuldades precisam ser
> preenchidas pelo grupo: este arquivo não substitui o documento entregue.

## 1. Segundo módulo: Consultas e Exames

Fluxo completo integrado ao banco (tabela `compromisso_medico`):

| Ação | Endpoint | Tela |
|---|---|---|
| Agendar consulta/exame | `POST /consultas` | Consultas e Exames → Agendar |
| Listar (próximos, anteriores, todos; filtro por tipo) | `GET /consultas?periodo=&tipo=` | Abas + filtro |
| Detalhar | `GET /consultas/{id}` | — |
| Editar / remarcar | `PUT /consultas/{id}` | Ícone de lápis |
| Remover | `DELETE /consultas/{id}` | Ícone de lixeira |

Pré-requisito novo: **vínculo cuidador-idoso** (`/vinculos`, tela "Meus Idosos").

## 2. Regras de negócio implementadas

| Código | Regra | Onde | Resposta em caso de violação |
|---|---|---|---|
| RN01 | Tipo do compromisso é apenas `CONSULTA` ou `EXAME` | `schemas/compromisso.py` | 422 |
| RN02 | Não é permitido agendar ou remarcar para data/hora no passado (fuso de Brasília) | `schemas/compromisso.py` + validação no formulário | 422 |
| RN03 | Um idoso não pode ter dois compromissos no mesmo horário | `services/compromisso.py` | 409 |
| RN04 | Especialidade/nome do exame obrigatório (2 a 100 caracteres) | schema + formulário | 422 |
| RN05 | IDOSO só acessa os próprios medicamentos e compromissos | `dependencies.py` | 403 |
| RN06 | CUIDADOR só acessa idosos vinculados a ele | `dependencies.py` | 403 |
| RN07 | Só CUIDADOR cria vínculo; o CPF precisa ser de um usuário IDOSO | `routers/vinculo.py` | 403 / 400 / 404 |
| RN08 | Vínculo duplicado não é permitido | `services/vinculo.py` | 409 |
| RN09 | Toda rota de dados exige token JWT válido | `dependencies.py` | 401 |
| RN10 | CPF aceito com ou sem máscara; armazenado só com dígitos | `schemas/auth.py` | 422 se ≠ 11 dígitos |

### Mudanças em relação ao planejamento inicial (justificar no documento)

- **Vínculo cuidador-idoso virou pré-requisito.** Sem ele não há como saber quais
  idosos um cuidador pode ver, e o controle de acesso (403) não teria base.
  A tabela já existia no schema; faltava a funcionalidade.
- **`agenda.py` foi unificado em `consultas.py`.** Os dois arquivos estavam vazios
  e tratavam da mesma tabela (`compromisso_medico`).
- **Frontend: removidas as telas herdadas do template** (perfis médico/paciente,
  calendário menstrual, chat, convites), que não correspondiam ao escopo do
  CliniRotina e acessavam outro banco diretamente.
- *(Grupo: comparar com o planejamento original e completar.)*

## 3. Matriz de perfis (o que demonstrar com prints)

| Ação | IDOSO | CUIDADOR vinculado | CUIDADOR sem vínculo | Sem login |
|---|---|---|---|---|
| Ver/editar próprios dados | ✅ | — | — | 401 → tela de login |
| Ver/editar dados do idoso | — | ✅ | **403** | 401 |
| Dados de outro idoso | **403** | **403** | **403** | 401 |
| Tela "Meus Idosos" (`/vinculos`) | **Página 403** | ✅ | ✅ | login |
| Criar vínculo via API | **403** | ✅ | ✅ | 401 |

## 4. Testes realizados

Automatizados (`pytest`, 30 casos, banco simulado em memória): `tests/`.
Rodar com `pip install -r requirements-dev.txt && pytest -q`.

| Fluxo | Caso | Esperado |
|---|---|---|
| Login | CPF com e sem máscara | 200 |
| Login | Senha errada | 401 "CPF ou senha inválidos" |
| Cadastro | CPF duplicado | 409 |
| Cadastro | Perfil inexistente | 422 |
| Acesso | Sem token / token inválido | 401 |
| Medicamentos | Idoso cria para si | 201 |
| Medicamentos | Cuidador sem vínculo cria para idoso | 403 |
| Medicamentos | Idoso acessa remédio de outro idoso (GET/PUT/DELETE/listar) | 403 |
| Medicamentos | ID malformado na URL | 422 (antes: 500) |
| Consultas | Agendamento válido | 201 |
| Consultas | Data no passado | 422 |
| Consultas | Mesmo horário para o mesmo idoso | 409 |
| Consultas | Tipo inválido / minúsculo | 422 / normalizado |
| Consultas | Cuidador sem informar idoso | 422 |
| Consultas | Outro idoso em GET/PUT/DELETE | 403 |
| Consultas | Excluir e consultar novamente | 204 → 404 |
| Vínculos | Idoso tenta criar | 403 |
| Vínculos | CPF inexistente / CPF de cuidador / duplicado | 404 / 400 / 409 |

## 5. Bugs encontrados e correções

| # | Bug | Causa | Correção |
|---|---|---|---|
| 1 | Após login o usuário voltava para a tela de login | `api.ts` salvava `data.user`, mas a API devolve os campos soltos | Sessão montada a partir de `id/nome/cpf/tipo_perfil` |
| 2 | Qualquer pessoa acessava/alterava medicamentos de qualquer idoso | Rotas não validavam o token | Dependência `get_current_user` + checagem de vínculo |
| 3 | `allowedRoles` não tinha efeito no frontend | `ProtectedRoute` ignorava a propriedade | Implementado, com página 403 |
| 4 | Login com CPF formatado falhava se o cadastro foi sem máscara (e vice-versa) | CPF salvo como digitado | Normalização para 11 dígitos |
| 5 | ID inválido na URL retornava erro 500 | String repassada ao banco como UUID | Parâmetros tipados como UUID (422) |
| 6 | Mensagens de erro genéricas ("Erro ao salvar") | `detail` da API ignorado | `mensagemErro()` exibe a mensagem real |
| 7 | Rótulo "Senha" não associado ao campo (acessibilidade) | `FormControl` envolvia a `div` | `FormControl` movido para o `Input` |
| 8 | Telas do template (médico/paciente) inacessíveis e incoerentes | Projeto base reaproveitado | Removidas |

## 6. Histórico real de commits (até a Sprint 04)

**Backend**

| Commit | Data | Autor | Mensagem |
|---|---|---|---|
| 95cbf48 | 2026-09-30 | Thiago Vinicius de Araújo | feat(sprint-04): configura deploy serverless na Vercel e CORS |
| f359300 | 2026-09-19 | newtsarthur | feat(sprint-03): complete implementation of medication CRUD, authentication, and profiles |
| 1c89a38 | 2026-09-19 | newtsarthur | initial commit, base routes and database schema |
| e82ffa8 | 2026-08-24 | Arthur Belo | Initial commit |

**Frontend**

| Commit | Data | Autor | Mensagem |
|---|---|---|---|
| 4734d48a | 2026-09-30 | Thiago Vinicius de Araújo | fix(sprint-04): corrige ícone do Login, adiciona rota /login e remove dist do versionamento |
| ab9972ab | 2026-09-26 | newtsarthur | chore: add gitignore and remove node_modules from version control |
| 8d9de87e | 2026-09-26 | newtsarthur | chore: remove node_modules from version control and update gitignore |
| 9e0b4c3d | 2026-09-26 | newtsarthur | feat(sprint-04): frontend structure, CliniRotina rebrand, and route preparation |
| 32871b44 | 2026-08-24 | Arthur Belo | Initial commit |

Para o documento, use print da página de commits do GitHub (exigência do professor),
e não apenas esta tabela.

## 7. Próximos passos (sugestão)

- Módulo de horários de rotina e registro de adesão (`horario_rotina`, `registro_adesao`).
- Notas de apoio do cuidador (`nota_apoio`).
- `/health` checar o banco de verdade (hoje sempre responde "connected").
- Testes de integração contra um banco Supabase de teste.
