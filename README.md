"# Creditas-PSD2-Simulator"



Before first launch, configure credentials in 'Configuration/{environment-dir}/entra.config.json}'. (Use 'entra.config.template.json' as a source, add your Creditas credentials and WSO2 client secret)

installation:
0) cd to working directory of the app
1) $env:NODE\_TLS\_REJECT\_UNAUTHORIZED="0"   // in PowerShell, just in case

2) python -m venv .venv

3) .venv\\Scripts\\pip install -r requirements.txt

4) .venv\\Scripts\\playwright install chromium
     or
   C:\\Users\\user\\Downloads\\Creditas-PSD2-Simulator-main\\.venv\\Scripts> .\\python.exe -m playwright install chromium

5) $env:NODE\_TLS\_REJECT\_UNAUTHORIZED="1"   // back to security

6) C:\\Users\\user\\Downloads\\Creditas-PSD2-Simulator-main\\start\_reflex.bat
