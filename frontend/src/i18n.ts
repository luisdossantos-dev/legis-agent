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

  // ══════════════════════════════════════════════════════════════
  // PIPELINE / WORKFLOW
  // ══════════════════════════════════════════════════════════════
  "pipeline.title": { en: "🔧 Agent Pipeline", fr: "🔧 Pipeline d'Agent" },
  "pipeline.description": { en: "Configure and run a multi-step agent pipeline on this document.", fr: "Configurez et exécutez un pipeline multi-étapes sur ce document." },
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
  "pipeline.toast.error": { en: "Pipeline execution failed", fr: "Échec de l'exécution du pipeline" },

  // ══════════════════════════════════════════════════════════════
  // KEYBOARD SHORTCUTS
  // ══════════════════════════════════════════════════════════════
  "shortcut.sendMessage": { en: "Ctrl+Enter to send", fr: "Ctrl+Entrée pour envoyer" },
  "shortcut.toggleTheme": { en: "Toggle theme", fr: "Changer le thème" },
  "shortcut.openSettings": { en: "Open settings", fr: "Ouvrir les paramètres" },
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
