# Static bundle browser acceptance

The screenshots show the static app at a nested URL with a checked two-product
bundle (`GCAVSv1` and `AQMv8`). Both products were built from independent local
source directories and manifest stores, and both use the same variable ID
(`TMP`). The Chromium run switched products, checked the second product's date
metadata, inspected a grid point, toggled the inspector, and opened the mobile
controls drawer. All requests stayed under the app directory; there were no
`/api/`, external, or browser console errors.

To repeat against a checked bundle, install Python Playwright and provide a
Chromium executable, then run from the repository root:

```bash
python -m pip install playwright
python frontend/scripts/static_acceptance.py \
  --site /path/to/static_site \
  --screenshots /path/to/screenshots
```

The run creates 1440×900, 1024×768, and 390×844 screenshots. Current captures:

- [1440×900 desktop](desktop-1440x900.png)
- [1024×768 desktop](desktop-1024x768.png)
- [390×844 mobile controls](mobile-390x844.png)
