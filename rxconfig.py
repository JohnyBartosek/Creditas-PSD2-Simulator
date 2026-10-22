import reflex as rx

config = rx.Config(
    app_name="psd2_app",
    telemetry_enabled=False,
    show_built_with_reflex=False,
    plugins=[
        rx.plugins.RadixThemesPlugin(
            theme=rx.theme(appearance="light", accent_color="indigo", radius="medium"),
        ),
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
