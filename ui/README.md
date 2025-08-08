# BirdNET-Pi Svelte UI

This directory contains a proof-of-concept Svelte + Tailwind UI for BirdNET-Pi. It mirrors the
existing PHP interface but is built as a modern single-page application.

## Development

```
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

## Production build

```
npm run build
```

The generated static assets can be served by the existing PHP backend.
