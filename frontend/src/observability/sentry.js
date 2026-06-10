export async function initSentry(app, router) {
  const dsn = process.env.VUE_APP_SENTRY_DSN;
  if (!dsn) {
    return;
  }

  try {
    const Sentry = await import("@sentry/vue");
    Sentry.init({
      app,
      dsn,
      environment: process.env.VUE_APP_ENVIRONMENT || process.env.NODE_ENV || "development",
      release: process.env.VUE_APP_RELEASE || undefined,
      integrations: router ? [] : [],
      tracesSampleRate: Number(process.env.VUE_APP_SENTRY_TRACES_SAMPLE_RATE || "0"),
    });
  } catch (error) {
    // Keep app boot resilient when Sentry isn't installed in local/dev setups.
    // eslint-disable-next-line no-console
    console.warn("Sentry initialization skipped:", error);
  }
}
