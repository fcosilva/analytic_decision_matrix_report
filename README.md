# Analytic Decision Matrix Report

Reporte operativo por proyectos (cuentas analiticas), independiente de MIS Builder.

Incluye soporte para compensacion interproyectos (reasignaciones) usando el diario contable `REASIG-ANA`.
Los reportes se guardan como registros reutilizables (versionables) para recalcular, imprimir y eliminar cuando ya no se necesiten.

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
2. Ir a `Contabilidad > Reportes > Matriz Decision Analitica`.

Nota:
- El menu aparece en Reportes de Contabilidad.
- No crea menu como aplicacion independiente.

## Uso rapido

1. Clic en `Nuevo` para crear una version del reporte.
2. Definir filtros:
- `Compania`
- `Fecha Desde` (opcional)
- `Fecha Hasta` (opcional, por defecto hoy)
- `Plan Analitico` (opcional)
- `Cuentas Analiticas` (opcional, una o varias)
- `Codigo diario reasignacion` (por defecto `REASIG-ANA`)
3. Clic en `Generar Matriz`.
4. Opcional: clic en `Imprimir PDF`.
5. Puedes volver a abrir el mismo registro luego para consultar o recalcular.

Comportamiento de fechas:
- Si `Fecha Desde` esta vacia, toma toda la historia disponible hasta `Fecha Hasta`.
- Si `Fecha Hasta` esta vacia, se usa la fecha actual.

## Criterio de calculo

`Ingreso` y `Egresos`:
- Se calculan desde apuntes contables posteados (`account_move_line`) con distribucion analitica.
- `Ingreso` usa cuentas de tipo ingreso.
- `Egresos` usa cuentas de tipo gasto.

## Reasignaciones interproyectos

- `Reasignacion (+)`: debitos en diario `REASIG-ANA`.
- `Reasignacion (-)`: creditos en diario `REASIG-ANA`.

Esto permite mover saldo entre proyectos para compensacion sin mezclarlo con ingresos o egresos reales.

## Cuentas por cobrar y cuentas por pagar (al corte)

`Ctas x Cob` y `Ctas x Pag` se calculan como residual abierto al corte (`Fecha Hasta`) de facturas posteadas:
- `Ctas x Cob`: facturas de cliente y notas de credito cliente pendientes de pago.
- `Ctas x Pag`: facturas de proveedor y notas de credito proveedor pendientes de pago.

El residual se distribuye a las cuentas analiticas segun la ponderacion analitica de las lineas de factura.
