/// <reference types="astro/client" />

type Runtime = import('@astrojs/cloudflare').Runtime<Env>;

interface Env {
  DATASETS: R2Bucket;
}

declare namespace App {
  interface Locals {
    runtime: Runtime;
  }
}
