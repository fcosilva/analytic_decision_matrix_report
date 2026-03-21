# Reporte Matriz de Decision Analitica

Reporte operativo por proyectos (cuentas analiticas), independiente de MIS Builder.

Incluye:
- Matriz de decision analitica reutilizable (se guarda como registro).
- Drill-down por documentos o por apuntes.
- Asistente de reasignacion analitica para mover saldo entre proyectos con trazabilidad.

## Alcance del reporte

Filas:
- Proyectos (`cuentas analiticas`).

Columnas:
- `Ingreso`
- `Ctas x Cob`
- `Reasignacion (+)`
- `Egresos`
- `Ctas x Pag`
- `Reasignacion (-)`
- `Saldo Devengado`
- `Saldo Efectivo`

Formulas:
- `Saldo Devengado = (Ingreso + Ctas x Cob + Reasignacion (+)) - (Egresos + Ctas x Pag + Reasignacion (-))`
- `Saldo Efectivo = (Ingreso + Reasignacion (+)) - (Egresos + Reasignacion (-))`

## Instalacion y acceso

1. Instalar modulo `analytic_decision_matrix_report`.
2. Ir a `Contabilidad > Reportes > Herramientas Analíticas`.

Submenus:
- `Matriz Decision Analitica`
- `Asistente Reasignación Analítica`

## Uso rapido de la matriz

1. Clic en `Nuevo` para crear una version del reporte.
2. Definir filtros:
- `Compania`
- `Fecha Desde` (opcional)
- `Fecha Hasta` (opcional, por defecto hoy)
- `Plan Analitico` (opcional)
- `Cuentas Analiticas` (opcional, una o varias)
- `Incluir reversados` (opcional, por defecto desactivado)
- `Desglose por documentos` (opcional, por defecto activado)
- `Codigo diario reasignacion` (por ejemplo `RASIG`)
3. Clic en `Generar Matriz`.
4. Opcional: clic en `Imprimir PDF`.

## Asistente de reasignacion

Flujo:
1. Completar:
- `Fecha contable`
- `Diario de reasignacion`
- `Cuenta puente`
- `Proyecto origen`
- `Proyecto destino`
- `Monto`
- `Motivo`
- `Soporte/Referencia` (opcional)
2. Clic en `Previsualizar`.
3. Revisar `Previsualización de Impacto` en formato matriz:
- Filas: `Origen: <proyecto>` y `Destino: <proyecto>`
- Columnas: `Saldo Devengado Antes`, `Saldo Devengado Después`, `Saldo Efectivo Antes`, `Saldo Efectivo Después`
4. Clic en `Confirmar y Contabilizar`.

Resultado:
- Se crea y publica un asiento contable balanceado.
- El registro queda en estado `Confirmado`.
- El asiento queda vinculado en el campo `Asiento Generado`.

## Criterio de fecha y validacion de saldo

Para el asistente, la validacion del saldo efectivo del proyecto origen se calcula con corte a la `Fecha contable` del movimiento, no a la fecha actual.

Comportamiento actual:
- Base de calculo: historico acumulado hasta `Fecha contable` (`date_to = self.date`).
- No usa rango `Desde/Hasta` en el asistente (solo fecha de corte).

Esto garantiza consistencia temporal entre:
- fecha de validacion,
- saldos previsualizados,
- y fecha del asiento generado.

## Criterios de calculo

`Ingreso` y `Egresos`:
- Se calculan desde apuntes contables posteados (`account_move_line`) con distribucion analitica.
- `Ingreso` usa cuentas de tipo ingreso.
- `Egresos` usa cuentas de tipo gasto.
- En facturas, `Ingreso`/`Egresos` consideran documentos pagados o en `in_payment` para criterio de efectivo.

`Ctas x Cob` y `Ctas x Pag`:
- Se calculan como residual abierto al corte (`Fecha Hasta`) en facturas posteadas.
- Se distribuyen por ponderacion analitica de lineas de factura.

Reasignaciones interproyectos:
- `Reasignacion (+)`: debitos en el diario de reasignacion configurado.
- `Reasignacion (-)`: creditos en el diario de reasignacion configurado.

## Drill-down

- Con `Desglose por documentos` activado:
- Ingreso/Egreso/Reasignacion abre documentos (`account.move`) y, cuando aplica 100% a hojas de gasto, abre `hr.expense.sheet`.
- CxC/CxP abre vista de residual analitico por documento.

- Con `Desglose por documentos` desactivado:
- Abre detalle contable (`account.move.line`).

## Reversas

- Por defecto se excluyen documentos reversados y sus reversas para evitar duplicidad en gestion.
- Si se activa `Incluir reversados`, se incluyen para fines de auditoria.

## Guias del modulo

- `docs/guia_reasignacion_analitica.md`
- `docs/especificacion_mvp_asistente_reasignacion.md`
