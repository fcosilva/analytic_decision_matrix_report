# Guia Operativa de Reasignacion Analitica

## Objetivo

Definir un criterio unico para mover saldo entre proyectos (cuentas analiticas) sin mezclar:
- ingresos reales
- egresos reales
- cuentas por cobrar/pagar

## Configuracion contable recomendada

### 1) Cuenta puente de reasignacion

- Codigo sugerido: `52040204`
- Nombre sugerido: `Reasignacion Analitica entre Proyectos`
- Tipo: `Gastos` (cuenta de resultados)
- Permitir imputacion manual: `Si`
- Conciliable: `No`

Nota:
- No usar cuentas de banco/caja.
- No usar cuentas por cobrar/pagar.
- No usar cuentas de patrimonio (grupos 35, 36, 37).

### 2) Diario de reasignacion

- Tipo de diario: `Varios`
- Nombre sugerido: `Reasignacion Analitica`
- Codigo corto sugerido: `RASIG` (maximo 5 caracteres)

## Regla de negocio

Cuando se mueve saldo de un proyecto origen a un proyecto destino:
- El origen debe disminuir su saldo.
- El destino debe aumentar su saldo.

Esto se logra con dos lineas en la misma cuenta puente:
- Debe en la analitica destino.
- Haber en la analitica origen.

## Estructura estandar del asiento

Ejemplo: mover `USD 1,000.00` de `Proyecto A` a `Proyecto B`.

- Linea 1:
  - Cuenta: `52040204`
  - Debe: `1,000.00`
  - Haber: `0.00`
  - Cuenta analitica: `Proyecto B` (destino)
- Linea 2:
  - Cuenta: `52040204`
  - Debe: `0.00`
  - Haber: `1,000.00`
  - Cuenta analitica: `Proyecto A` (origen)

Efecto:
- Mayor general: neto `0.00` (misma cuenta en debe/haber).
- Analitico: se traslada saldo de A hacia B.
- Matriz de decision: se ve como `Reasignacion (-)` en A y `Reasignacion (+)` en B.

## Flujo en el sistema (actual)

Ruta:
- `Contabilidad > Reportes > Herramientas Analíticas > Asistente Reasignación Analítica`

Pasos:
1. Crear registro nuevo y completar datos.
2. Clic en `Previsualizar`.
3. Revisar la tabla `Previsualización de Impacto`:
   - Filas: `Origen: <proyecto>` y `Destino: <proyecto>`.
   - Columnas: `Saldo Devengado Antes`, `Saldo Devengado Después`, `Saldo Efectivo Antes`, `Saldo Efectivo Después`.
4. Clic en `Confirmar y Contabilizar`.
5. Verificar campo `Asiento Generado`.

## Criterio de fecha (clave)

La validacion de saldo efectivo del proyecto origen se hace con corte a la `Fecha contable` de la reasignacion, no con fecha actual.

Criterio aplicado:
- Base historica acumulada hasta la fecha del movimiento.
- Si la fecha contable es `31/12/2025`, el control de saldo usa informacion hasta ese corte.

## Plantilla de glosa y referencia

Usar este formato:

```text
REF: REASIG {AAAA-MM} {PROY_ORIGEN}->{PROY_DESTINO}
CONCEPTO: Reasignacion analitica de saldo entre proyectos.
MOTIVO: {motivo concreto}
DETALLE: Se traslada {MONTO} desde {PROY_ORIGEN} hacia {PROY_DESTINO}.
SOPORTE: {acta / aprobacion / ticket}
RESPONSABLE: {nombre}
```

## Checklist previo a confirmar

- Confirmar proyecto origen y destino.
- Confirmar monto y soporte aprobado.
- Confirmar uso del diario `RASIG` (o diario configurado).
- Confirmar que ambas lineas usan la misma cuenta puente.
- Confirmar que cada linea tiene su cuenta analitica correcta.
- Confirmar fecha contable correcta (el control de saldo se hace a ese corte).

## Errores comunes a evitar

- Usar cuentas de banco/caja para reasignar.
- Usar cuentas por cobrar/pagar para reasignar.
- Usar cuentas de patrimonio (35, 36, 37).
- Hacer una sola linea (siempre deben ser dos lineas balanceadas).
- Omitir cuenta analitica en alguna linea.
- Validar saldo "a hoy" cuando el asiento es historico.
