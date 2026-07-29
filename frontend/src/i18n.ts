/**
 * Legis Agent — Internationalization (i18n)
 *
 * Supports English (en) and French (fr).
 * All user-facing strings should be defined here.
 *
 * Usage:
 *   import { t, useLanguage } from "../i18n";
 *   t("welcome.title")
 *   t("chat.welcome", "doc.pdf")
 *   t("documents.pagesChunks", "5", "22")
 */

// ── Translations ────────────────────────────────────────────────
// Each key maps to { en: "...", fr: "..." }
// or a function that returns such a map.

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const translations: Record<string, any> = {
  // ══════════════════════════════════════════════════════════════
  // GENERAL / COMMON
  // ══════════════════════════════════════════════════════════════
  "app.name": { en: "⚖️ Legis Agent", fr: "⚖️ Legis Agent" },
  "app.loading": { en: "Loading...", fr: "Chargement..." },
  "app.refresh": { en: "↻ Refresh", fr: "↻ Actualiser" },
  "app.cancel": { en: "Cancel", fr: "Annuler" },
  "app.save": { en: "Save", fr: "Enregistrer" },
  "app.close": { en: "Close", fr: "Fermer" },
  "app.copy": { en: "Copy to Clipboard", fr: "Copier dans le presse-papier" },
  "app.error": { en: "Error", fr: "Erreur" },
  "app.unknown": { en: "Unknown", fr: "Inconnu" },
  "app.noData": { en: "No data", fr: "Aucune donnée" },

  // ══════════════════════════════════════════════════════════════
  // HEADER
  // ══════════════════════════════════════════════════════════════
  "header.status.checking": { en: "Checking...", fr: "Vérification..." },
  "header.status.connected": { en: "Backend connected", fr: "Backend connecté" },
  "status.noApiKey": { en: "Backend connected (no API key)", fr: "Backend connecté (pas de clé API)" },
  "header.status.disconnected": { en: "Backend disconnected", fr: "Backend déconnecté" },
  "header.email": { en: "Email", fr: "Email" },
  "header.classify": { en: "Classify", fr: "Classifier" },
  "header.actions": { en: "Actions", fr: "Actions" },
  "header.review": { en: "Review", fr: "Réviser" },
  "header.dashboard": { en: "Dashboard", fr: "Tableau de bord" },
  "header.users": { en: "Users", fr: "Utilisateurs" },
  "header.pipeline": { en: "Pipeline", fr: "Pipeline" },
  "header.docs": { en: "Docs", fr: "Docs" },
  "header.settings": { en: "⚙️ Settings", fr: "⚙️ Paramètres" },
  "header.refresh": { en: "↻ Refresh documents", fr: "↻ Actualiser les documents" },
  "header.theme": { en: "Toggle theme", fr: "Changer le thème" },
  "header.light": { en: "☀️ Light", fr: "☀️ Clair" },
  "header.dark": { en: "🌙 Dark", fr: "🌙 Sombre" },

  // ══════════════════════════════════════════════════════════════
  // WELCOME
  // ══════════════════════════════════════════════════════════════
  "welcome.title": { en: "Welcome to Legis Agent", fr: "Bienvenue sur Legis Agent" },
  "welcome.description": { en: "Upload a legal document (PDF, DOCX or TXT) to get started. The agent will analyze the document and you can chat with it to refine the analysis.", fr: "Téléchargez un document juridique (PDF, DOCX ou TXT) pour commencer. L'agent analysera le document et vous pourrez discuter avec lui pour affiner l'analyse." },
  "welcome.noApiKey": { en: "⚠️ No API key configured.", fr: "⚠️ Aucune clé API configurée." },
  "welcome.openSettings": { en: "Open Settings", fr: "Ouvrir les paramètres" },
  "welcome.toAddOne": { en: "to add one.", fr: "pour en ajouter une." },

  // ══════════════════════════════════════════════════════════════
  // DOCUMENTS
  // ══════════════════════════════════════════════════════════════
  "documents.title": { en: "Documents", fr: "Documents" },
  "documents.empty": { en: "No documents uploaded yet.", fr: "Aucun document téléchargé pour l'instant." },
  "documents.noApiKey": { en: "No API key configured. Analyze and Chat buttons are disabled.", fr: "Aucune clé API configurée. Les boutons Analyser et Discuter sont désactivés." },
  "documents.apiKeyRequired": { en: "🔑 API key required — Open Settings to enable Analyze & Chat", fr: "🔑 Clé API requise — Ouvrez Paramètres pour activer Analyser et Discuter" },
  "documents.indexing": { en: "⏳ indexing…", fr: "⏳ indexation…" },
  "documents.error": { en: "❌ error", fr: "❌ erreur" },
  "documents.analyze": { en: "Analyze", fr: "Analyser" },
  "documents.chat": { en: "Chat", fr: "Discuter" },
  "documents.email": { en: "📧 Email", fr: "📧 Email" },
  "documents.pagesChunks": (p: string, c: string) => ({ en: `${p} pages · ${c} chunks`, fr: `${p} pages · ${c} fragments` }),
  "documents.btnTooltip.noApiKey": { en: "🔑 Configure API key in Settings to enable actions", fr: "🔑 Configurez une clé API dans Paramètres pour activer les actions" },
  "documents.btnTooltip.indexing": { en: "⏳ Document is still indexing...", fr: "⏳ Document en cours d'indexation..." },

  // ══════════════════════════════════════════════════════════════
  // UPLOAD
  // ══════════════════════════════════════════════════════════════
  "upload.ariaLabel": { en: "Upload a legal document", fr: "Télécharger un document juridique" },
  "upload.uploading": { en: "Uploading and processing...", fr: "Téléchargement et traitement..." },
  "upload.dragDrop": { en: "Drag & drop a document or click here", fr: "Glissez-déposez un document ou cliquez ici" },
  "upload.formats": { en: "PDF · DOCX · TXT", fr: "PDF · DOCX · TXT" },

  // ══════════════════════════════════════════════════════════════
  // CHAT
  // ══════════════════════════════════════════════════════════════
  "chat.description": { en: "Ask about the document using the legal agent", fr: "Posez des questions sur le document à l'aide de l'agent juridique" },
  "chat.placeholder": { en: "Type your legal question...", fr: "Tapez votre question juridique..." },
  "chat.references": { en: "References:", fr: "Références :" },
  "chat.thinking": { en: "Thinking...", fr: "Réflexion..." },
  "chat.send": { en: "Send", fr: "Envoyer" },
  "chat.error": { en: "Error communicating with the agent", fr: "Erreur de communication avec l'agent" },
  "chat.title": (f: string) => ({ en: `Legal Chat — ${f}`, fr: `Discussion juridique — ${f}` }),
  "chat.welcome": (f: string) => ({ en: `Hi, I'm the legal assistant. You can ask me about "${f}". How can I help you?`, fr: `Bonjour, je suis l'assistant juridique. Vous pouvez me poser des questions sur "${f}". Comment puis-je vous aider ?` }),
  "chat.sendAria": { en: "Send message", fr: "Envoyer le message" },
  "chat.sendingAria": { en: "Sending...", fr: "Envoi..." },

  // ══════════════════════════════════════════════════════════════
  // ANALYSIS
  // ══════════════════════════════════════════════════════════════
  "analysis.analyzing": { en: "Analyzing document...", fr: "Analyse du document..." },
  "analysis.title": { en: "Document Analysis", fr: "Analyse du document" },
  "analysis.summary": { en: "Summary", fr: "Résumé" },
  "analysis.parties": { en: "Parties", fr: "Parties" },
  "analysis.dates": { en: "Key Dates", fr: "Dates clés" },
  "analysis.amounts": { en: "Amounts", fr: "Montants" },
  "analysis.clauses": { en: "Clauses", fr: "Clauses" },
  "analysis.risks": { en: "Risks", fr: "Risques" },
  "analysis.toast.error": { en: "Analysis Failed", fr: "Échec de l'analyse" },

  // ══════════════════════════════════════════════════════════════
  // EMAIL DRAFT
  // ══════════════════════════════════════════════════════════════
  "email.title": { en: "📧 Draft an Email", fr: "📧 Rédiger un Email" },
  "email.actType.escritura": { en: "Deed of Sale", fr: "Acte de Vente" },
  "email.actType.poder": { en: "Power of Attorney", fr: "Procuration" },
  "email.actType.testamento": { en: "Last Will & Testament", fr: "Testament" },
  "email.actType.matrimonio": { en: "Civil Marriage", fr: "Mariage Civil" },
  "email.actType.general": { en: "General Communication", fr: "Communication Générale" },
  "email.actTypeLabel": { en: "Act Type", fr: "Type d'acte" },
  "email.language": { en: "Language", fr: "Langue" },
  "email.sensitivity": { en: "Sensitivity", fr: "Sensibilité" },
  "email.customQuery": { en: "Custom Instructions", fr: "Instructions personnalisées" },
  "email.useDocContext": { en: "Use document context", fr: "Utiliser le contexte du document" },
  "email.generate": { en: "Generate Email", fr: "Générer l'Email" },
  "email.generating": { en: "Generating...", fr: "Génération..." },
  "email.showRaw": { en: "Raw JSON", fr: "JSON brut" },
  "email.result.to": { en: "To", fr: "À" },
  "email.toast.error": { en: "Failed to generate email", fr: "Échec de la génération de l'email" },

  // ══════════════════════════════════════════════════════════════
  // EMAIL CLASSIFIER
  // ══════════════════════════════════════════════════════════════
  "classifier.title": { en: "📬 Classify an Email", fr: "📬 Classifier un Email" },
  "classifier.description": { en: "Analyze an email and classify it into the appropriate category.", fr: "Analysez un email et classez-le dans la catégorie appropriée." },
  "classifier.from": { en: "From", fr: "De" },
  "classifier.subject": { en: "Subject", fr: "Sujet" },
  "classifier.body": { en: "Body", fr: "Corps" },
  "classifier.bodyRequired": { en: "Email body is required.", fr: "Le corps de l'email est requis." },
  "classifier.classify": { en: "Classify Email", fr: "Classifier l'Email" },
  "classifier.classifying": { en: "Classifying...", fr: "Classification..." },
  "classifier.result": { en: "Result", fr: "Résultat" },
  "classifier.category": { en: "Category", fr: "Catégorie" },
  "classifier.confidence": { en: "Confidence", fr: "Confiance" },
  "classifier.method": { en: "Method", fr: "Méthode" },
  "classifier.toast.error": { en: "Classification failed", fr: "Échec de la classification" },
  "category.cliente_nuevo": { en: "🆕 New Client", fr: "🆕 Nouveau Client" },
  "category.seguimiento_escritura": { en: "📝 Deed Follow-up", fr: "📝 Suivi d'Acte" },
  "category.consulta_hipoteca": { en: "🏠 Mortgage Inquiry", fr: "🏠 Demande de Prêt" },
  "category.notificacion_banco": { en: "🏦 Bank Notification", fr: "🏦 Notification Bancaire" },
  "category.spam": { en: "🚫 Spam", fr: "🚫 Spam" },
  "category.interno": { en: "🏢 Internal", fr: "🏢 Interne" },

  // ══════════════════════════════════════════════════════════════
  // SETTINGS
  // ══════════════════════════════════════════════════════════════
  "settings.title": { en: "⚙️ Settings", fr: "⚙️ Paramètres" },
  "settings.provider": { en: "LLM Provider", fr: "Fournisseur LLM" },
  "settings.apiKey": { en: "API Key", fr: "Clé API" },
  "settings.model": { en: "Model", fr: "Modèle" },
  "settings.saveActivate": { en: "Save & Activate", fr: "Enregistrer et Activer" },
  "settings.saving": { en: "Saving...", fr: "Enregistrement..." },
  "settings.configured": { en: "✓ This provider has been configured and is active", fr: "✓ Ce fournisseur est configuré et actif" },
  "settings.notConfigured": { en: "⚠️ This provider is not yet configured — enter an API key above", fr: "⚠️ Ce fournisseur n'est pas encore configuré — saisissez une clé API ci-dessus" },
  "settings.keepKey": { en: "✓ Previously configured (leave empty to keep existing key)", fr: "✓ Déjà configuré (laissez vide pour conserver la clé existante)" },
  "settings.keyRequired": { en: "Enter an API key to configure this provider.", fr: "Saisissez une clé API pour configurer ce fournisseur." },
  "settings.configError": { en: "Could not load configuration.", fr: "Impossible de charger la configuration." },
  "settings.saveSuccess": (provider: string) => ({ en: `✅ ${provider} configured successfully!`, fr: `✅ ${provider} configuré avec succès !` }),
  "settings.saveError": { en: "Failed to save.", fr: "Échec de l'enregistrement." },
  "settings.keyNote": { en: "API keys are stored in memory for the current session. You may need to re-enter if the backend restarts.", fr: "Les clés API sont stockées en mémoire pour la session en cours. Vous devrez peut-être les ressaisir si le backend redémarre." },
  "settings.persistsNote": { en: "💡 Tip: API keys persist in backend config file. On restart, the key is reloaded automatically.", fr: "💡 Astuce : Les clés API persistent dans le fichier de configuration. Au redémarrage, la clé est rechargée automatiquement." },
  "settings.getKeyFrom": (provider: string) => ({ en: `Get your ${provider} key from the dashboard`, fr: `Obtenez votre clé ${provider} depuis le tableau de bord` }),

  // ══════════════════════════════════════════════════════════════
  // TOAST
  // ══════════════════════════════════════════════════════════════
  "toast.apiKeyWarning.title": { en: "API Key Required", fr: "Clé API Requise" },
  "toast.apiKeyWarning.message": { en: "Configure an API key in Settings to enable document analysis and AI chat features.", fr: "Configurez une clé API dans Paramètres pour activer l'analyse de documents et les fonctions IA." },
  "toast.apiKeyMissing.title": { en: "API Key Missing", fr: "Clé API Manquante" },
  "toast.apiKeyMissing.analyze": { en: "Set an API key in Settings before analyzing documents.", fr: "Définissez une clé API dans Paramètres avant d'analyser." },
  "toast.apiKeyMissing.chat": { en: "Set an API key in Settings before using the chat.", fr: "Définissez une clé API dans Paramètres avant d'utiliser le chat." },
  "toast.apiKeyMissing.email": { en: "Set an API key in Settings before drafting emails.", fr: "Définissez une clé API dans Paramètres avant de rédiger." },

  // ══════════════════════════════════════════════════════════════
  // LANGUAGE
  // ══════════════════════════════════════════════════════════════
  "language.en": { en: "English", fr: "Anglais" },
  "language.fr": { en: "French", fr: "Français" },

  // ══════════════════════════════════════════════════════════════
  // DASHBOARD
  // ══════════════════════════════════════════════════════════════
  "dashboard.title": { en: "📊 Cost & Usage Dashboard", fr: "📊 Tableau de bord Coûts & Utilisation" },
  "dashboard.card.totalCost": { en: "Total Cost", fr: "Coût Total" },
  "dashboard.card.monthlyEst": { en: "Monthly Est.", fr: "Estimation Mensuelle" },
  "dashboard.card.operations": { en: "Operations", fr: "Opérations" },
  "dashboard.card.tokens": { en: "Total Tokens", fr: "Tokens Totaux" },
  "dashboard.card.errors": { en: "Errors", fr: "Erreurs" },
  "dashboard.card.models": { en: "Models Used", fr: "Modèles Utilisés" },
  "dashboard.chart.dailyCost": { en: "💰 Daily Cost (Last 30 Days)", fr: "💰 Coût Quotidien (30 derniers jours)" },
  "dashboard.chart.dailyCalls": { en: "📞 Daily Calls", fr: "📞 Appels Quotidiens" },
  "dashboard.chart.modelUsage": { en: "🤖 Model Usage", fr: "🤖 Utilisation des Modèles" },
  "dashboard.chart.costByModel": { en: "💰 Cost by Model", fr: "💰 Coût par Modèle" },
  "dashboard.chart.latencyDist": { en: "⏱️ Latency Distribution", fr: "⏱️ Distribution de la Latence" },
  "dashboard.table.latency": { en: "⏱️ Latency by Operation (ms)", fr: "⏱️ Latence par Opération (ms)" },
  "dashboard.table.success": { en: "✅ Success Rates", fr: "✅ Taux de Réussite" },
  "dashboard.noCostData": { en: "No cost data recorded yet.", fr: "Aucune donnée de coût enregistrée." },
  "dashboard.noCallData": { en: "No call data recorded yet.", fr: "Aucune donnée d'appel enregistrée." },
  "dashboard.pricePerMillion": { en: "Price/M tokens", fr: "Prix/M tokens" },
  "dashboard.loadError": { en: "Failed to load dashboard data", fr: "Échec du chargement des données" },

  // ══════════════════════════════════════════════════════════════
  // PIPELINE / WORKFLOW
  // ══════════════════════════════════════════════════════════════
  "pipeline.title": { en: "🔧 Agent Pipeline", fr: "🔧 Pipeline d'Agent" },
  "pipeline.description": { en: "Configure and run a multi-step agent pipeline on this document.", fr: "Configurez et exécutez un pipeline multi-étapes sur ce document." },
  "pipeline.descriptionNoDoc": { en: "Select a document first, then open Pipeline to configure and run a multi-step workflow.", fr: "Sélectionnez d'abord un document, puis ouvrez Pipeline pour configurer et exécuter un workflow multi-étapes." },
  "pipeline.presets": { en: "Quick Presets", fr: "Préréglages Rapides" },
  "pipeline.steps": { en: "Pipeline Steps", fr: "Étapes du Pipeline" },
  "pipeline.run": { en: "▶️ Run Pipeline", fr: "▶️ Exécuter le Pipeline" },
  "pipeline.running": { en: "Running pipeline...", fr: "Exécution du pipeline..." },
  "pipeline.result": { en: "Pipeline Result", fr: "Résultat du Pipeline" },
  "pipeline.steps.extract": { en: "📋 Extract", fr: "📋 Extraire" },
  "pipeline.steps.extract.desc": { en: "Quick metadata extraction (parties, dates, amounts)", fr: "Extraction rapide des métadonnées (parties, dates, montants)" },
  "pipeline.steps.analyze": { en: "🔍 Analyze", fr: "🔍 Analyser" },
  "pipeline.steps.analyze.desc": { en: "Full structured document analysis", fr: "Analyse structurée complète du document" },
  "pipeline.steps.review": { en: "⚖️ Review", fr: "⚖️ Réviser" },
  "pipeline.steps.review.desc": { en: "Legal review of the draft", fr: "Révision juridique du brouillon" },
  "pipeline.steps.draft": { en: "✍️ Draft", fr: "✍️ Rédiger" },
  "pipeline.steps.draft.desc": { en: "Generate response/email draft", fr: "Générer un brouillon de réponse/email" },
  "pipeline.steps.send": { en: "📨 Send", fr: "📨 Envoyer" },
  "pipeline.steps.send.desc": { en: "Final formatting and assembly", fr: "Mise en forme et assemblage final" },
  "pipeline.stepsExecuted": { en: "Steps executed", fr: "Étapes exécutées" },
  "pipeline.processingTime": { en: "Processing time", fr: "Temps de traitement" },
  "pipeline.query": { en: "Query", fr: "Requête" },
  "pipeline.queryOptional": { en: "(optional)", fr: "(facultatif)" },
  "pipeline.queryPlaceholder": { en: "Analyze this legal document and extract its main components.", fr: "Analysez ce document juridique et extrayez ses composants principaux." },
  "pipeline.type": { en: "Type:", fr: "Type :" },
  "pipeline.unknown": { en: "Unknown", fr: "Inconnu" },
  "pipeline.stepsCount": (n: string) => ({ en: `${n} steps`, fr: `${n} étapes` }),
  "pipeline.confirm": (n: string, f: string) => ({
    en: `Run ${n} pipeline step${n === "1" ? "" : "s"} on "${f}"?\n\nThis may take 30–90 seconds.`,
    fr: `Exécuter ${n} étape${n === "1" ? "" : "s"} du pipeline sur "${f}" ?\n\nCela peut prendre 30 à 90 secondes.`,
  }),
  "pipeline.elapsed": (s: string) => ({ en: `${s}s`, fr: `${s}s` }),
  "pipeline.toast.error": { en: "Pipeline execution failed", fr: "Échec de l'exécution du pipeline" },

  // ══════════════════════════════════════════════════════════════
  // KEYBOARD SHORTCUTS
  // ══════════════════════════════════════════════════════════════
  "shortcut.sendMessage": { en: "Ctrl+Enter to send", fr: "Ctrl+Entrée pour envoyer" },
  "shortcut.toggleTheme": { en: "Toggle theme", fr: "Changer le thème" },
  "shortcut.openSettings": { en: "Open settings", fr: "Ouvrir les paramètres" },

  // ══════════════════════════════════════════════════════════════
  // DOCUMENTATION
  // ══════════════════════════════════════════════════════════════
  "docs.title": { en: "Documentation", fr: "Documentation" },
  "docs.description": { en: "Learn how to use every feature of Legis Agent.", fr: "Apprenez à utiliser chaque fonctionnalité de Legis Agent." },
  "docs.overview": { en: "🏠 Overview", fr: "🏠 Aperçu" },
  "docs.overviewText": { en: "Legis Agent is an AI-powered legal document analysis and drafting assistant. Upload documents (PDF, DOCX, TXT), analyze them with AI, chat about their contents, draft emails, classify incoming correspondence, review clauses, and run multi-step agent pipelines — all from a single desktop interface.", fr: "Legis Agent est un assistant d'analyse et de rédaction de documents juridiques alimenté par l'IA. Téléchargez des documents (PDF, DOCX, TXT), analysez-les avec l'IA, discutez de leur contenu, rédigez des emails, classez la correspondance entrante, révisez des clauses et exécutez des pipelines d'agents multi-étapes — le tout depuis une seule interface de bureau." },
  "docs.uploadTitle": { en: "📄 Document Upload & Analysis", fr: "📄 Téléchargement et Analyse" },
  "docs.uploadText": { en: "Upload legal documents and get AI-powered analysis including parties, dates, amounts, clauses, and risk assessment.", fr: "Téléchargez des documents juridiques et obtenez une analyse IA incluant les parties, dates, montants, clauses et évaluation des risques." },
  "docs.steps": { en: "Steps:", fr: "Étapes :" },
  "docs.uploadStep1": { en: "Drag & drop a file or click the upload area", fr: "Glissez-déposez un fichier ou cliquez sur la zone de téléchargement" },
  "docs.uploadStep2": { en: "Wait for the document to be processed and indexed", fr: "Attendez que le document soit traité et indexé" },
  "docs.uploadStep3": { en: "Click Analyze to run AI analysis", fr: "Cliquez sur Analyser pour lancer l'analyse IA" },
  "docs.uploadStep4": { en: "Use Chat to ask follow-up questions about the document", fr: "Utilisez Chat pour poser des questions sur le document" },
  "docs.supportedFormats": { en: "Supported formats", fr: "Formats supportés" },
  "docs.chatTitle": { en: "💬 Chat with Documents", fr: "💬 Discuter avec les Documents" },
  "docs.chatText": { en: "Ask questions about your documents in natural language. The AI assistant has full context of the document and can answer specific legal questions, summarize clauses, and extract information.", fr: "Posez des questions sur vos documents en langage naturel. L'assistant IA a le contexte complet du document et peut répondre à des questions juridiques spécifiques, résumer des clauses et extraire des informations." },
  "docs.shortcuts": { en: "Keyboard Shortcuts", fr: "Raccourcis Clavier" },
  "docs.shortcutSend": { en: "Send message", fr: "Envoyer le message" },
  "docs.shortcutUpload": { en: "Go to upload", fr: "Aller au téléchargement" },
  "docs.shortcutPalette": { en: "Open command palette", fr: "Ouvrir la palette de commandes" },
  "docs.shortcutSettings": { en: "Open settings", fr: "Ouvrir les paramètres" },
  "docs.shortcutNav": { en: "Navigate views", fr: "Naviguer entre les vues" },
  "docs.shortcutClose": { en: "Close modals / go back", fr: "Fermer les fenêtres / retour" },
  "docs.emailTitle": { en: "📧 Email Drafting", fr: "📧 Rédaction d'Email" },
  "docs.emailText": { en: "Draft professional legal emails based on document context. Choose from act types (Deed of Sale, Power of Attorney, Last Will, etc.), set language and sensitivity, and optionally include document context.", fr: "Rédigez des emails juridiques professionnels basés sur le contexte du document. Choisissez parmi les types d'actes (Acte de Vente, Procuration, Testament, etc.), définissez la langue et la sensibilité, et incluez optionnellement le contexte du document." },
  "docs.emailBullet1": { en: "Select the act type that matches your document", fr: "Sélectionnez le type d'acte correspondant à votre document" },
  "docs.emailBullet2": { en: "Choose the output language", fr: "Choisissez la langue de sortie" },
  "docs.emailBullet3": { en: "Set sensitivity level (Normal or Private)", fr: "Définissez le niveau de sensibilité (Normal ou Privé)" },
  "docs.classifyTitle": { en: "📬 Email Classification", fr: "📬 Classification d'Email" },
  "docs.classifyText": { en: "Classify incoming emails into categories: New Client, Deed Follow-up, Mortgage Inquiry, Bank Notification, Spam, or Internal. The classifier uses AI to analyze the email content and subject.", fr: "Classez les emails entrants dans des catégories : Nouveau Client, Suivi d'Acte, Demande de Prêt, Notification Bancaire, Spam ou Interne. Le classificateur utilise l'IA pour analyser le contenu et le sujet de l'email." },
  "docs.classifyBullet1": { en: "Enter the sender, subject, and body of the email", fr: "Saisissez l'expéditeur, le sujet et le corps de l'email" },
  "docs.classifyBullet2": { en: "Click Classify to get the predicted category and confidence score", fr: "Cliquez sur Classifier pour obtenir la catégorie prédite et le score de confiance" },
  "docs.actionTitle": { en: "⚡ Action Detection", fr: "⚡ Détection d'Actions" },
  "docs.actionText": { en: "Analyze email content to detect required actions such as drafting a response, scheduling a meeting, or forwarding to a colleague. The detector extracts the intent and suggests appropriate next steps.", fr: "Analysez le contenu des emails pour détecter les actions requises telles que la rédaction d'une réponse, la planification d'une réunion ou le transfert à un collègue. Le détecteur extrait l'intention et suggère les prochaines étapes appropriées." },
  "docs.reviewTitle": { en: "🔍 Clause Review", fr: "🔍 Révision de Clauses" },
  "docs.reviewText": { en: "Review notarial clauses against predefined risk checklists. Select a clause type to see the applicable checklist items and get AI-powered risk assessments for each criterion.", fr: "Révisez les clauses notariales par rapport aux listes de contrôle de risques prédéfinies. Sélectionnez un type de clause pour voir les éléments de contrôle applicables et obtenez des évaluations de risques basées sur l'IA." },
  "docs.pipelineTitle": { en: "🔧 Agent Pipeline", fr: "🔧 Pipeline d'Agent" },
  "docs.pipelineText": { en: "Run multi-step agent workflows on your documents. Combine Extract, Analyze, Review, Draft, and Send steps in any order to create custom automation pipelines.", fr: "Exécutez des workflows d'agents multi-étapes sur vos documents. Combinez les étapes Extraire, Analyser, Réviser, Rédiger et Envoyer dans n'importe quel ordre pour créer des pipelines d'automatisation personnalisés." },
  "docs.pipelineStep1": { en: "Select a document from the sidebar", fr: "Sélectionnez un document dans la barre latérale" },
  "docs.pipelineStep2": { en: "Choose a preset template or customize your steps", fr: "Choisissez un modèle prédéfini ou personnalisez vos étapes" },
  "docs.pipelineStep3": { en: "Reorder steps using ◀ ▶ buttons", fr: "Réorganisez les étapes avec les boutons ◀ ▶" },
  "docs.pipelineStep4": { en: "Add an optional custom query and click Run", fr: "Ajoutez une requête personnalisée facultative et cliquez sur Exécuter" },
  "docs.pipelinePresets": { en: "Presets available", fr: "Préréglages disponibles" },
  "docs.pipelinePresetsText": { en: "Full Analysis (all 5 steps), Quick Extract (extract only), Analyze + Draft, Review + Send", fr: "Analyse Complète (5 étapes), Extraction Rapide (extraction seule), Analyser + Rédiger, Réviser + Envoyer" },
  "docs.dashboardTitle": { en: "📊 Cost & Usage Dashboard", fr: "📊 Tableau de bord Coûts & Utilisation" },
  "docs.dashboardText": { en: "Monitor token usage, API costs, latency, and error rates. Configure your own price per million tokens to get accurate cost estimates.", fr: "Surveillez l'utilisation des tokens, les coûts API, la latence et les taux d'erreur. Configurez votre propre prix par million de tokens pour obtenir des estimations de coûts précises." },
  "docs.dashboardBullet1": { en: "Set your Price/M tokens in the dashboard header", fr: "Définissez votre Prix/M tokens dans l'en-tête du tableau de bord" },
  "docs.dashboardBullet2": { en: "View daily cost and call charts (30-day history)", fr: "Consultez les graphiques de coûts et d'appels quotidiens (historique 30 jours)" },
  "docs.dashboardBullet3": { en: "Monitor latency by operation and success rates", fr: "Surveillez la latence par opération et les taux de succès" },
  "docs.usersTitle": { en: "🔐 User Management", fr: "🔐 Gestion des Utilisateurs" },
  "docs.usersText": { en: "Manage users, roles (Admin, Notaire, Stagiaire), and offices. View audit logs for GDPR compliance. Export or delete user data on request.", fr: "Gérez les utilisateurs, les rôles (Admin, Notaire, Stagiaire) et les offices. Consultez les journaux d'audit pour la conformité RGPD. Exportez ou supprimez les données des utilisateurs sur demande." },
  "docs.settingsTitle": { en: "⚙️ Settings", fr: "⚙️ Paramètres" },
  "docs.settingsText": { en: "Configure your LLM provider (API key, model) and toggle between light/dark themes. Settings persist across sessions.", fr: "Configurez votre fournisseur LLM (clé API, modèle) et basculez entre les thèmes clair/sombre. Les paramètres persistent entre les sessions." },
  "docs.langThemeTitle": { en: "🌐 Language & Theme", fr: "🌐 Langue et Thème" },
  "docs.langThemeText1": { en: "Switch between English and French using the dropdown in the header. The interface updates immediately without reload.", fr: "Basculez entre l'anglais et le français à l'aide du menu déroulant dans l'en-tête. L'interface se met à jour immédiatement sans rechargement." },
  "docs.langThemeText2": { en: "Toggle between light and dark themes using the ☀️/🌙 button in the header. Light theme is the default.", fr: "Basculez entre les thèmes clair et sombre à l'aide du bouton ☀️/🌙 dans l'en-tête. Le thème clair est le thème par défaut." },
};

// ── Helpers ─────────────────────────────────────────────────────

export type Lang = "en" | "fr";

// Restore language preference from localStorage, fallback to browser language or English
const savedLang = (typeof window !== "undefined" ? localStorage.getItem("legis-lang") : null) as Lang | null;
const browserLang = typeof navigator !== "undefined" ? (navigator.language?.startsWith("fr") ? "fr" as Lang : "en" as Lang) : "en";
let _currentLang: Lang = savedLang || browserLang || "en";
const _listeners: Array<(lang: Lang) => void> = [];

export function setLanguage(lang: Lang) {
  _currentLang = lang;
  if (typeof window !== "undefined") {
    localStorage.setItem("legis-lang", lang);
  }
  _listeners.forEach((fn) => fn(lang));
}

export function getLanguage(): Lang {
  return _currentLang;
}

export function subscribe(fn: (lang: Lang) => void) {
  _listeners.push(fn);
  return () => {
    const idx = _listeners.indexOf(fn);
    if (idx >= 0) _listeners.splice(idx, 1);
  };
}

/** Translate a key. Dynamic keys accept extra args like t("chat.title", filename). */
export function t(key: string, ...args: string[]): string {
  const entry = translations[key];
  if (entry === undefined) {
    console.warn(`[i18n] Missing key: "${key}"`);
    return key;
  }
  const map = typeof entry === "function" ? entry(...args) : entry;
  return map[_currentLang] ?? map["en"] ?? key;
}

import { useState, useEffect } from "react";

export function useLanguage() {
  const [lang, setLangState] = useState<Lang>(_currentLang);
  useEffect(() => {
    return subscribe((l) => setLangState(l));
  }, []);
  return { lang, setLanguage, t, _: t as typeof t };
}
