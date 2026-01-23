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

const tiersCollection = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    tierNumber: z.number().int().min(1).max(3),
    planName: z.string(),
    shortDescription: z.string(),
    priceUsdMonthly: z.number().int().min(0),
    updatedAt: z.date().optional(),
  }),
});

export const collections = {
  updates: updatesCollection,
  tiers: tiersCollection,
};
