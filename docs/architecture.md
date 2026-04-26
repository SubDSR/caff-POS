# Arquitectura de carpetas

## Criterio aplicado

La app `cafeteria` quedó separada por responsabilidades para reducir acoplamiento y facilitar crecimiento:

- `application/`: coordinación del estado de sesión y navegación HTTP.
- `domain/`: reglas puras del negocio y constantes del POS.
- `infrastructure/`: acceso a MySQL y detalles técnicos externos.
- `presentation/`: vistas HTTP y composición de respuestas Django.
- `templates/cafeteria/`: UI separada por niveles de Atomic Design.
- `tests/`: pruebas desacopladas del código productivo.

## Estructura propuesta

```text
cafeteria/
  application/
  domain/
  infrastructure/
    persistence/
      mysql/
  presentation/
    http/
      views/
  static/
  templates/
    cafeteria/
      atoms/
      molecules/
      organisms/
      layouts/
      pages/
  templatetags/
  tests/
```

## Convenciones

- La lógica de negocio no depende de Django cuando no es necesario.
- Las vistas solo orquestan casos de uso, sesión y renderizado.
- El acceso a datos queda encapsulado en `infrastructure/persistence/mysql/catalog.py`.
- Los templates de página se apoyan en componentes más pequeños reutilizables.
- Las nuevas funcionalidades deben entrar por módulo antes que crecer archivos monolíticos.
