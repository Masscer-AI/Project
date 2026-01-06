# Guía de Referencia de Estilos - Masscer AI

Este documento define los criterios de diseño y estilos utilizados en la aplicación Masscer AI para mantener consistencia visual en todas las vistas y componentes.

## Librerías y Tecnologías

- **Framework CSS**: Tailwind CSS
- **Iconos**: SVG personalizados (definidos en `src/assets/svgs`)
- **Animaciones**: CSS animations y Tailwind transitions
- **Internacionalización**: react-i18next

## Esquema de Colores

### Colores Principales

- **Fondo Principal**: `rgb(0, 0, 0)` o `#000000`
- **Fondo Secundario (Cards/Containers)**: 
  - `bg-[rgba(255,255,255,0.05)]` - Fondo translúcido para cards
  - `bg-[rgba(35,33,39,0.5)]` - Fondo para botones y elementos interactivos
- **Texto Principal**: `text-white` o `rgb(255, 255, 255)`
- **Texto Secundario**: `text-[rgb(156,156,156)]` - Para texto menos importante
- **Bordes**: 
  - `border-[rgba(255,255,255,0.1)]` - Bordes sutiles para cards
  - `border-[rgba(156,156,156,0.3)]` - Bordes para botones

### Colores de Estado

- **Habilitado/Activo**: 
  - Fondo: `bg-green-500/20`
  - Texto: `text-green-400`
  - Borde: `border-green-500/30`
- **Deshabilitado/Inactivo**: 
  - Fondo: `bg-red-500/20`
  - Texto: `text-red-400`
  - Borde: `border-red-500/30`
- **Pendiente**: 
  - Fondo: `bg-yellow-500/20` o similar
  - Texto: `text-yellow-400`

### Colores de Botones

- **Estado Normal**: 
  - Fondo: `bg-[rgba(35,33,39,0.5)]`
  - Texto: `text-white`
  - Borde: `border-[rgba(156,156,156,0.3)]`
  - Hover: `hover:bg-[rgba(35,33,39,0.8)]`
- **Estado Activo/Hovered**: 
  - Fondo: `bg-white`
  - Texto: `text-gray-800`
  - Borde: `border-[rgba(156,156,156,0.3)]`
- **Deshabilitado**: 
  - Fondo: `bg-[rgba(35,33,39,0.3)]`
  - Texto: `text-[rgb(156,156,156)]`
  - Borde: `border-[rgba(156,156,156,0.2)]`
  - Opacidad: `opacity-50`

## Tipografía

### Títulos Principales
- **Clase**: `text-4xl font-bold text-white tracking-tight`
- **Sombra de Texto**: `style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}`
- **Alineación**: `text-center`
- **Espaciado**: `mb-8`

### Subtítulos
- **Clase**: `text-xl font-bold text-white`
- **Margen izquierdo**: `ml-2` (cuando hay badges a la izquierda)

### Texto Secundario
- **Clase**: `text-sm text-[rgb(156,156,156)]`
- **Para labels**: `text-sm font-medium text-[rgb(156,156,156)]`

### Texto de Carga/Estado Vacío
- **Clase**: `text-center py-10 text-lg text-[rgb(156,156,156)]` o `text-xl text-[rgb(156,156,156)]`

## Componentes

### Cards/Contenedores

```tsx
className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-6 shadow-lg"
```

- **Padding**: `p-6` (moderado) o `p-8` (más espacioso)
- **Border Radius**: `rounded-2xl`
- **Backdrop Blur**: `backdrop-blur-md`
- **Sombra**: `shadow-lg`
- **Gap interno**: `gap-4` o `gap-6` para flex/grid

### Botones Principales

```tsx
className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border ${
  isHovered
    ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]'
    : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
}`}
style={{ transform: 'none' }}
```

- **Padding**: `px-6 py-3` (estándar) o `px-8 py-3` (botones más grandes)
- **Border Radius**: `rounded-full`
- **Font**: `font-normal text-sm`
- **Cursor**: `cursor-pointer`
- **Transform**: `style={{ transform: 'none' }}` - Para evitar movimiento en hover
- **Transiciones**: Sin `transition-colors` para evitar movimiento visual

### Botones de Acción Secundarios

```tsx
className={`px-4 py-3 rounded-full font-normal text-sm cursor-pointer border ${...}`}
```

- **Padding**: `px-4 py-3` (más compactos)

### Badges/Etiquetas de Estado

```tsx
className={`px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap ${
  enabled
    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
    : 'bg-red-500/20 text-red-400 border border-red-500/30'
}`}
```

- **Padding**: `px-4 py-2`
- **Font**: `text-xs font-semibold`
- **Whitespace**: `whitespace-nowrap`

### Inputs y Formularios

```tsx
className="w-full p-3 bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.1)] rounded-lg text-white placeholder-[rgb(156,156,156)] focus:outline-none focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]"
```

- **Padding**: `p-3`
- **Border Radius**: `rounded-lg`
- **Focus Ring**: `focus:ring-2 focus:ring-[rgba(110,91,255,0.5)]`

### Modales

```tsx
// Backdrop
className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"

// Contenedor del Modal
className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-8 max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-lg"
```

- **Z-index**: `z-50`
- **Padding del contenedor**: `p-8`
- **Max width**: `max-w-2xl` o `max-w-7xl` según el caso
- **Overflow**: `overflow-y-auto` para contenido largo

## Layout y Espaciado

### Contenedor Principal

```tsx
<main className="d-flex pos-relative h-viewport">
  <div className="dashboard-container relative">
    <div className="max-w-7xl mx-auto px-4">
      {/* Contenido */}
    </div>
  </div>
</main>
```

- **Max Width**: `max-w-7xl`
- **Padding horizontal**: `px-4`
- **Centrado**: `mx-auto`

### Grids

- **Cards en Grid**: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`
- **Gap estándar**: `gap-6` o `gap-4`

### Espaciado Vertical

- **Entre secciones**: `mb-8` o `mb-12`
- **Entre elementos**: `gap-4` o `gap-6`

## Efectos y Animaciones

### Backdrop Blur
- **Cards**: `backdrop-blur-md`
- **Modales backdrop**: `backdrop-blur-sm`

### Transiciones
- **Hover en filas de tabla**: `hover:bg-[rgba(255,255,255,0.05)] transition-colors`
- **Cursor en filas clickeables**: `cursor-pointer`

### Animaciones Personalizadas
- **Sidebar**: `animate-[appear-left_500ms_forwards]` (definida en `index.css`)

## Sidebar

```tsx
className="bg-[rgba(35,33,39,0.5)] backdrop-blur-md fixed md:relative left-0 top-0 h-screen z-[3] flex flex-col w-[min(350px,100%)] p-3 gap-2.5 border-r border-[rgba(255,255,255,0.1)]"
```

- **Ancho**: `w-[min(350px,100%)]`
- **Padding**: `p-3`
- **Gap**: `gap-2.5`
- **Z-index**: `z-[3]`

## Tablas

### Filas Clickeables
```tsx
<tr 
  className="cursor-pointer hover:bg-[rgba(255,255,255,0.05)] transition-colors"
  onClick={() => navigate(...)}
>
```

### Celdas
- **Padding**: `p-3` o `px-4 py-3`
- **Border bottom**: `border-b border-[rgba(255,255,255,0.1)]`

## Tags/Etiquetas en Cards

```tsx
<span 
  className="conversation-tag"
  style={{ backgroundColor: tagColor }}
>
  {tagName}
</span>
```

- **Estilo**: Color de fondo dinámico basado en el color de la tag
- **Clase base**: `conversation-tag` (definida en CSS)

## Consideraciones Importantes

1. **Sin movimiento visual**: Los botones NO deben usar `transition-colors` para evitar movimiento durante cambios de color
2. **Bordes consistentes**: Todos los botones deben tener el mismo borde en estados normal y hover
3. **Padding con !important**: Si hay conflictos con CSS global, usar `!px-*` o `!py-*`
4. **Text Shadow en títulos**: Solo para títulos principales de página
5. **Backdrop blur**: Usar consistentemente en cards y modales para efecto glassmorphism
6. **Colores de tags**: Dinámicos basados en el campo `color` del modelo Tag

## Ejemplos de Uso

### Botón Estándar
```tsx
const [hovered, setHovered] = useState(false);

<button
  className={`px-6 py-3 rounded-full font-normal text-sm cursor-pointer border ${
    hovered
      ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]'
      : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
  }`}
  style={{ transform: 'none' }}
  onMouseEnter={() => setHovered(true)}
  onMouseLeave={() => setHovered(false)}
>
  Texto del Botón
</button>
```

### Card Estándar
```tsx
<div className="bg-[rgba(255,255,255,0.05)] backdrop-blur-md border border-[rgba(255,255,255,0.1)] rounded-2xl p-6 flex flex-col gap-4 shadow-lg">
  <h3 className="text-xl font-bold text-white ml-2">Título</h3>
  <p className="text-sm text-[rgb(156,156,156)]">Contenido</p>
</div>
```

### Título de Página
```tsx
<h1 className="text-4xl font-bold mb-8 text-center text-white tracking-tight" style={{ textShadow: '0 2px 8px rgba(110, 91, 255, 0.2)' }}>
  Título de la Página
</h1>
```

