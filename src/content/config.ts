import { defineCollection, z } from 'astro:content';

const updatesCollection = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.date(),
    description: z.string(),
    author: z.string().default('Instrumetriq Team'),
  }),
});

export const collections = {
  updates: updatesCollection,
};
