# Wistia in GoHighLevel

GHL funnel pages are a Nuxt/Vue app. Custom HTML is hydrated after tracking scripts run. The Aurora `<wistia-player>` web component plus `player.js` and `embed/{id}.js` (`type="module"`) often never mount on a cold first visit. Refresh then works because the scripts are cached. GTmetrix can still score 99: it paints the CSS swatch (`:not(:defined)`) and never requests `player.js`.

**Fix:** native iframe. It is a separate document. Vue cannot kill it.

## Hero / above-the-fold VSL

Do **not** put a `.reveal` class on `.video-shell`.

```html
<div class="video-shell">
  <iframe
    src="https://fast.wistia.net/embed/iframe/WISTIA_ID?seo=false&amp;videoFoam=true"
    title="VIDEO TITLE"
    allow="autoplay; fullscreen"
    allowtransparency="true"
    frameborder="0"
    scrolling="no"
    loading="eager"
    fetchpriority="high"
  ></iframe>
</div>
```

CSS (shared sheet):

```css
.video-shell{position:relative;aspect-ratio:16/9;overflow:hidden}
.video-shell iframe{display:block;position:absolute;inset:0;width:100%;height:100%;border:0}
```

## Head tracking

Allowed:

```html
<link rel="preconnect" href="https://fast.wistia.net" crossorigin>
<link rel="preconnect" href="https://fast.wistia.com" crossorigin>
<link rel="dns-prefetch" href="https://fast.wistia.net">
```

Forbidden in GHL head/footer tracking:

- `https://fast.wistia.com/player.js`
- `https://fast.wistia.com/embed/{id}.js` with `type="module"`
- `<wistia-player>`

Below-fold Wistia (FAQ, testimonials): same iframe with `loading="lazy"` and no `fetchpriority`.

## Defer Typeform (required on VSL + sales pages)

Typeform's renderer is hundreds of KB and starves Wistia on first visit. Replace any immediate `embed.js` script with:

```html
<script>
  (function(){
    var target=document.querySelector('[data-tf-live]');
    if(!target){return;}
    var loaded=false;
    function loadTypeform(){
      if(loaded){return;}
      loaded=true;
      var s=document.createElement('script');
      s.src='https://embed.typeform.com/next/embed.js';
      s.async=true;
      document.body.appendChild(s);
    }
    if(!('IntersectionObserver' in window)){loadTypeform();return;}
    var io=new IntersectionObserver(function(entries){
      if(entries[0]&&entries[0].isIntersecting){loadTypeform();io.disconnect();}
    },{rootMargin:'600px'});
    io.observe(target);
  })();
</script>
```

## First-load test

Private window, published GHL URL, no refresh. Pass = player chrome visible. Fail = blurred swatch or empty box until reload.
