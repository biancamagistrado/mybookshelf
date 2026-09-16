
export interface Genre {
  id: number;
  name: string;
  slug: string;
}

export type EnrichmentState = "pending" | "enriched" | "not_found" | "failed";

export interface Book {
  id: number;
  goodreads_id: number | null;
  source: string;
  title: string;
  author: string;
  additional_authors: string | null;
  isbn: string | null;
  isbn13: string | null;
  publisher: string | null;
  binding: string | null;
  number_of_pages: number | null;
  year_published: number | null;
  original_publication_year: number | null;
  exclusive_shelf: string;
  bookshelves: string | null;
  my_rating: number | null;
  average_rating: number | null;
  date_read: string | null;
  date_added: string | null;
  read_count: number | null;
  owned_copies: number | null;
  my_review: string | null;
  cover_url: string | null;
  description: string | null;
  enrichment_status: EnrichmentState;
  enrichment_source: string | null;
  enriched_at: string | null;
  created_at: string;
  updated_at: string;
  genres: Genre[];
}

export interface BookPage {
  items: Book[];
  total: number;
  limit: number;
  offset: number;
}

export interface ShelfCount {
  shelf: string;
  count: number;
}

export interface FacetCount {
  value: string;
  count: number;
}

export interface ImportResult {
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
  warnings: string[];
  enrichment_queued: boolean;
}

export interface ListImportResult {
  created: number;
  already_on_shelf: string[];
  not_found: string[];
}

export interface EnrichmentStatus {
  pending: number;
  enriched: number;
  not_found: number;
  failed: number;
  running: boolean;
}

export interface TopItem {
  name: string;
  count: number;
}

export interface YearCount {
  year: number;
  count: number;
}

export interface RatingBucket {
  rating: number;
  count: number;
}

export interface Stats {
  total_books: number;
  books_read: number;
  books_read_this_year: number;
  currently_reading: number;
  to_read: number;
  pages_read: number;
  average_rating_given: number | null;
  top_genres: TopItem[];
  top_authors: TopItem[];
  books_per_year: YearCount[];
  rating_distribution: RatingBucket[];
}

export type SortField =
  | "title"
  | "author"
  | "date_read"
  | "date_added"
  | "my_rating"
  | "average_rating";

export interface BookFilters {
  shelf: string | null;
  author: string | null;
  genre: string | null;
  search: string;
  sort: SortField;
  direction: "asc" | "desc";
}

export interface NewBook {
  title: string;
  author: string;
  exclusive_shelf: string;
  genres: string[];
  number_of_pages: number | null;
  isbn13: string | null;
  date_read: string | null;
  cover_url?: string | null;
  publisher?: string | null;
  year_published?: number | null;
}

export interface BookPatch {
  title?: string;
  author?: string;
  exclusive_shelf?: string;
  my_rating?: number | null;
  genres?: string[];
  number_of_pages?: number | null;
  isbn13?: string | null;
  date_read?: string | null;
  cover_url?: string | null;
  description?: string | null;
  my_review?: string | null;
}

export interface BookSuggestion {
  title: string;
  author: string;
  isbn13: string | null;
  cover_url: string | null;
  genres: string[];
  number_of_pages: number | null;
  year_published: number | null;
  publisher: string | null;
  source: string;
}
