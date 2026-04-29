import { defineCollection, z } from 'astro:content';

const books = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    original: z.string(),
    author: z.string(),
    year: z.number(),
    publisher: z.string().optional(),
    cover: z.string(),
    douban: z.string().url(),
    order: z.number(),
  }),
});

export const collections = { books };
