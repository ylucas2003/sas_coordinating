# Documentação da Canvas LMS REST API

Espelho local da API REST do Canvas (a mesma que o app **Canvas Student** consome por baixo), organizada em Markdown para consulta offline e referência durante a integração do SAS.

- **Base URL:** `https://<sua-instituição>.instructure.com/api/v1/`
- **Auth:** header `Authorization: Bearer <token>` — ver [guides/oauth.md](guides/oauth.md)
- **Paginação:** header `Link` (rel="next") — ver [guides/pagination.md](guides/pagination.md)
- **Fonte:** doc oficial da Instructure + repo [instructure/canvas-lms](https://github.com/instructure/canvas-lms) (`doc/api`)
- **Formato:** referência de endpoints convertida de HTML→MD; guias são os `.md` originais do repo.

## ⭐ Mais relevantes pro SAS

| Recurso | Por quê |
|---|---|
| [Submissions](reference/submissions.md) | Nota de cada aluno por avaliação — campos `score`, `grade`, `missing`, `excused`, `late`, `workflow_state`. **Distingue ausência de zero real.** |
| [Assignments](reference/assignments.md) | Cada simulado/prova é um assignment (`points_possible`, `due_at`). |
| [Enrollments](reference/enrollments.md) | Liga aluno↔curso↔seção; traz o `sis_user_id`. |
| [Courses](reference/courses.md) | Listar cursos e alunos (`/courses/:id/users`). |
| [Quiz Submissions](reference/quiz_submissions.md) · [Quiz Statistics](reference/quiz_statistics.md) | Resultados e estatística por questão dos simulados (Quizzes clássicos). |
| [Sections](reference/sections.md) | Suas turmas / `Section`. |

## 🔑 Autenticação & chaves

- [Access Tokens](reference/access_tokens.md)
- [InstAccess tokens](reference/inst_access_tokens.md)
- [JWTs](reference/jw_ts.md)
- [API Token Scopes](reference/api_token_scopes.md)
- [Developer Keys](reference/developer_keys.md)
- [Developer Key Account Bindings](reference/developer_key_account_bindings.md)
- [Public JWK](reference/public_jwk.md)
- [Authentication Providers](reference/authentication_providers.md)
- [Logins](reference/logins.md)

## 🏫 Cursos & turmas

- [Courses](reference/courses.md)
- [Sections](reference/sections.md)
- [Enrollments](reference/enrollments.md)
- [Enrollment Terms](reference/enrollment_terms.md)
- [Course Pace](reference/course_pace.md)
- [Course Reports](reference/course_reports.md)
- [Course Audit log](reference/course_audit_log.md)
- [Blueprint Courses](reference/blueprint_courses.md)
- [Favorites](reference/favorites.md)
- [Tabs](reference/tabs.md)

## 👤 Usuários

- [Users](reference/users.md)
- [User Observees](reference/user_observees.md)
- [Admins](reference/admins.md)
- [Communication Channels](reference/communication_channels.md)
- [Notification Preferences](reference/notification_preferences.md)
- [Bookmarks](reference/bookmarks.md)
- [Conversations](reference/conversations.md)

## 📊 Notas & avaliações

- [Assignments](reference/assignments.md)
- [Assignment Groups](reference/assignment_groups.md)
- [Assignment Extensions](reference/assignment_extensions.md)
- [Submissions](reference/submissions.md)
- [Submission Comments](reference/submission_comments.md)
- [Gradebook History](reference/gradebook_history.md)
- [Grade Change Log](reference/grade_change_log.md)
- [Grading Standards](reference/grading_standards.md)
- [Grading Periods](reference/grading_periods.md)
- [Grading Period Sets](reference/grading_period_sets.md)
- [Late Policy](reference/late_policy.md)
- [Moderated Grading](reference/moderated_grading.md)
- [Custom Gradebook Columns](reference/custom_gradebook_columns.md)
- [What If Grades](reference/what_if_grades.md)
- [Peer Reviews](reference/peer_reviews.md)
- [Rubrics](reference/rubrics.md)
- [Line Items](reference/line_items.md)
- [Score](reference/score.md)
- [Result](reference/result.md)
- [Learning Object Dates](reference/learning_object_dates.md)

## 🎯 Outcomes (competências)

- [Outcomes](reference/outcomes.md)
- [Outcome Groups](reference/outcome_groups.md)
- [Outcome Results](reference/outcome_results.md)
- [Outcome Imports](reference/outcome_imports.md)
- [Proficiency Ratings](reference/proficiency_ratings.md)

## 📝 Quizzes & Simulados

- [Quizzes](reference/quizzes.md)
- [Quiz Submissions](reference/quiz_submissions.md)
- [Quiz Questions](reference/quiz_questions.md)
- [Quiz Question Groups](reference/quiz_question_groups.md)
- [Quiz Reports](reference/quiz_reports.md)
- [Quiz Statistics](reference/quiz_statistics.md)
- [Quiz Extensions](reference/quiz_extensions.md)
- [Quiz IP Filters](reference/quiz_ip_filters.md)
- [Quiz Assignment Overrides](reference/quiz_assignment_overrides.md)
- [Quiz Submission Events](reference/quiz_submission_events.md)
- [Quiz Submission Files](reference/quiz_submission_files.md)
- [Quiz Submission Questions](reference/quiz_submission_questions.md)
- [Quiz Submission User List](reference/quiz_submission_user_list.md)
- [Course Quiz Extensions](reference/course_quiz_extensions.md)
- [LiveAssessments](reference/live_assessments.md)

## 📚 Conteúdo & comunicação

- [Modules](reference/modules.md)
- [Pages](reference/pages.md)
- [Files](reference/files.md)
- [Discussion Topics](reference/discussion_topics.md)
- [Announcements](reference/announcements.md)
- [Announcement External Feeds](reference/announcement_external_feeds.md)
- [Collaborations](reference/collaborations.md)
- [Conferences](reference/conferences.md)
- [Content Exports](reference/content_exports.md)
- [Content Migrations](reference/content_migrations.md)
- [Content Shares](reference/content_shares.md)
- [Media Objects](reference/media_objects.md)
- [Search](reference/search.md)
- [Smart Search](reference/smart_search.md)
- [BlockEditorTemplate](reference/block_editor_template.md)
- [CommMessages](reference/comm_messages.md)

## 👥 Grupos & calendário

- [Groups](reference/groups.md)
- [Group Categories](reference/group_categories.md)
- [Appointment Groups](reference/appointment_groups.md)
- [Calendar Events](reference/calendar_events.md)
- [Planner](reference/planner.md)

## ⚙️ Contas & administração

- [Accounts](reference/accounts.md)
- [Account Calendars](reference/account_calendars.md)
- [Account Notifications](reference/account_notifications.md)
- [Account Reports](reference/account_reports.md)
- [Roles](reference/roles.md)
- [Feature Flags](reference/feature_flags.md)
- [Brand Configs](reference/brand_configs.md)
- [Shared Brand Configs](reference/shared_brand_configs.md)
- [Content Security Policy Settings](reference/content_security_policy_settings.md)
- [Services](reference/services.md)
- [Error Reports](reference/error_reports.md)
- [History](reference/history.md)
- [Progress](reference/progress.md)
- [Blackout Dates](reference/blackout_dates.md)
- [Temporary Enrollment Pairings](reference/temporary_enrollment_pairings.md)

## 🔗 SIS, LTI & integrações

- [SIS Imports](reference/sis_imports.md)
- [SIS Import Errors](reference/sis_import_errors.md)
- [SIS Integration](reference/sis_integration.md)
- [External Tools](reference/external_tools.md)
- [LTI Registrations](reference/lti_registrations.md)
- [LTI Resource Links](reference/lti_resource_links.md)
- [LTI Launch Definitions](reference/lti_launch_definitions.md)
- [Names and Role](reference/names_and_role.md)

## 🗳️ Polls

- [Polls](reference/polls.md)
- [PollChoices](reference/poll_choices.md)
- [Poll Sessions](reference/poll_sessions.md)
- [PollSubmissions](reference/poll_submissions.md)

## 🕵️ Plágio & originalidade

- [Originality Reports](reference/originality_reports.md)
- [Plagiarism Detection Platform Assignments](reference/plagiarism_detection_platform_assignments.md)
- [Plagiarism Detection Platform Users](reference/plagiarism_detection_platform_users.md)
- [Plagiarism Detection Submissions](reference/plagiarism_detection_submissions.md)
- [Webhooks Subscriptions for Plagiarism Platform](reference/webhooks_subscriptions_for_plagiarism_platform.md)

## 🗂️ ePortfolios

- [ePortfolios](reference/e_portfolios.md)
- [ePub Exports](reference/e_pub_exports.md)

## 📦 Outros

- [Authentications Log](reference/authentications_log.md)

## 📖 Guias & conceitos

- [Visão geral oficial (README)](guides/README.md)
- [Papéis (roles) do Canvas](guides/canvas_roles.md)
- [Changelog](guides/changelog.md)
- [Documentos compostos](guides/compound_documents.md)
- [LTI — Content Item](guides/content_item.md)
- [Developer Keys](guides/developer_keys.md)
- [Atributos de endpoint](guides/endpoint_attributes.md)
- [Upload de arquivos](guides/file_uploads.md)
- [GraphQL API](guides/graphql.md)
- [JWT Access Tokens](guides/jwt_access_tokens.md)
- [Masquerading (agir como outro usuário)](guides/masquerading.md)
- [OAuth2 — fluxo de autenticação](guides/oauth.md)
- [OAuth2 — endpoints](guides/oauth_endpoints.md)
- [IDs de objetos & SIS IDs](guides/object_ids.md)
- [Paginação](guides/pagination.md)
- [Platform Notification Service](guides/pns.md)
- [Provisioning](guides/provisioning.md)
- [LTI — registro](guides/registration.md)
- [Formato SIS CSV](guides/sis_csv.md)
- [Subscriptions (apêndice)](guides/subscriptions_appendix.md)
- [Rate limiting / throttling](guides/throttling.md)
- [xAPI](guides/xapi.md)

---
*122 recursos de referência + 22 guias. Gerado a partir da documentação pública do Canvas LMS.*