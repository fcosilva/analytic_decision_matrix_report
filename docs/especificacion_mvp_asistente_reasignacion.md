# Especificacion MVP - Asistente de Reasignacion Analitica

## Objetivo

Reducir errores y tiempo operativo en la creacion de diarios de reasignacion analitica, guiando al usuario con un flujo simple y validaciones automaticas.

## Alcance MVP (implementado)

Caso cubierto:
- `1 proyecto origen -> 1 proyecto destino`
- `monto fijo`
- `generacion y contabilizacion automatica de asiento`

No cubre en fase 1:
- distribucion a multiples proyectos
- reparto porcentual automatico
- motor de aprobaciones multinivel
- reversa asistida del movimiento

## Flujo funcional

1. **Configurar**
- Compania
- Fecha contable
- Diario de reasignacion (tipo `Varios`)
- Cuenta puente
- Proyecto origen
- Proyecto destino
- Monto
- Motivo
- Soporte/Referencia (opcional)

2. **Previsualizar**
- Calcula impacto con corte a `Fecha contable`
- Muestra matriz de impacto:
  - Filas: `Origen: <proyecto>` y `Destino: <proyecto>`
  - Columnas: `Saldo Devengado Antes`, `Saldo Devengado Después`, `Saldo Efectivo Antes`, `Saldo Efectivo Después`
- Muestra advertencia si el origen no tiene saldo efectivo suficiente

3. **Confirmar y Contabilizar**
- Crea `account.move` tipo `entry`
- Publica el asiento (`posted`)
- Vincula el asiento al registro del asistente (`move_id`)
- Cambia estado a `done`

## Reglas de negocio MVP

1. Proyecto origen y destino deben ser distintos.
2. Monto mayor a cero.
3. Diario debe ser tipo `Varios`.
4. Diario y cuenta puente deben pertenecer a la misma compania.
5. Las dos lineas contables usan la misma cuenta puente.
6. No permite confirmar nuevamente si ya existe asiento vinculado.
7. Bloquea confirmacion si el monto excede saldo efectivo del origen al corte.

## Criterio de fecha (decision clave)

La validacion del saldo efectivo se realiza con corte a la `Fecha contable` del registro (`self.date`), no a la fecha actual.

Criterio aplicado internamente:
- Proxy de matriz con `date_to = self.date`
- Base historica acumulada hasta ese corte
- `include_reversed = False` para esta validacion

## Estructura del asiento generado

- Linea Debe:
  - Cuenta puente (`52040204` sugerida)
  - Analitica destino
  - Monto = X
- Linea Haber:
  - Cuenta puente (`52040204` sugerida)
  - Analitica origen
  - Monto = X

## Modelo y estado tecnico

Modelo principal:
- `analytic.reassignment.wizard` (`models.Model`, persistente)

Estado:
- `draft`
- `preview`
- `done`

Campos principales:
- `name` (secuencia `analytic.reassignment.wizard`)
- `company_id`, `date`
- `journal_id`, `bridge_account_id`
- `analytic_origin_id`, `analytic_destination_id`
- `amount`, `reason`, `support_ref`
- `move_id`, `state`
- campos de previsualizacion (`before/after` de devengado y efectivo)

## UI actual

Menu:
- `Contabilidad > Reportes > Herramientas Analíticas > Asistente Reasignación Analítica`

Vista formulario:
- Header con estado y botones: `Previsualizar`, `Confirmar y Contabilizar`
- Bloque de datos generales
- Bloque de detalle de reasignacion
- Bloque `Previsualización de Impacto` en tabla/matriz

## Seguridad (actual)

- Usuario interno contable puede crear/previsualizar/confirmar (segun permisos del modelo y contabilidad).
- Se apoya en permisos nativos de `account.move` para publicar el asiento.

## Criterios de aceptacion (UAT)

1. Usuario crea una reasignacion sin construir manualmente el asiento.
2. El asiento queda balanceado y posteado.
3. La matriz principal refleja `Reasignacion (+)` y `Reasignacion (-)` en proyectos correctos.
4. La previsualizacion respeta la fecha contable de corte.
5. El registro conserva trazabilidad (`motivo`, `soporte`, `asiento generado`).

## Siguiente fase sugerida

1. Reasignacion `1 -> N` por porcentaje.
2. Plantillas por tipo de regularizacion.
3. Flujo de aprobacion por monto.
4. Reversion asistida del asiento generado.
