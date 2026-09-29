import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://pzuroocozhjqqabvmlqv.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'sb_publishable_7gWfxCrcbpGl41kKD3zE-w_k7srwGpG'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
