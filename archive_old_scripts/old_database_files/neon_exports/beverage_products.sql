--
-- PostgreSQL database dump
--

\restrict 1xhI45hUeHzkBYHBbCSiqKZ8OeFvp0JUqpn6QJVas09tMCnSV2WU3mmH4hMcCOM

-- Dumped from database version 18.0
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.beverage_products DROP CONSTRAINT IF EXISTS beverage_products_pkey;
ALTER TABLE IF EXISTS public.beverage_products ALTER COLUMN item_id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.beverage_products_item_id_seq;
DROP TABLE IF EXISTS public.beverage_products;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: beverage_products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.beverage_products (
    item_id integer NOT NULL,
    item_name character varying(255) NOT NULL,
    category character varying(100),
    unit_price numeric(10,2) NOT NULL,
    stock_quantity integer,
    image_url text,
    image_path text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    our_cost numeric(10,2),
    default_markup_pct numeric(5,2) DEFAULT 35,
    deposit_amount numeric(10,2) DEFAULT 0,
    fees_amount numeric(10,2) DEFAULT 0,
    gst_included boolean DEFAULT false,
    description character varying(500) DEFAULT NULL::character varying
);


--
-- Name: beverage_products_item_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.beverage_products_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: beverage_products_item_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.beverage_products_item_id_seq OWNED BY public.beverage_products.item_id;


--
-- Name: beverage_products item_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_products ALTER COLUMN item_id SET DEFAULT nextval('public.beverage_products_item_id_seq'::regclass);


--
-- Data for Name: beverage_products; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.beverage_products (item_id, item_name, category, unit_price, stock_quantity, image_url, image_path, created_at, our_cost, default_markup_pct, deposit_amount, fees_amount, gst_included, description) FROM stdin;
1044	Barefoot Chardonnay 1L	Champagne	20.52	0	\N	\N	2026-01-08 14:42:13.491013	14.36	35.00	0.10	0.00	f	Barefoot Chardonnay wine - 1L bottle
1045	Barefoot Moscato 1L	Champagne	21.72	0	\N	\N	2026-01-08 14:42:13.491013	15.20	35.00	0.10	0.00	f	Barefoot Moscato wine - 1L bottle
1046	Barefoot Pinot Grigio 1L	Champagne	22.04	0	\N	\N	2026-01-08 14:42:13.491013	15.43	35.00	0.10	0.00	f	Barefoot Pinot Grigio wine - 1L bottle
1047	Corona (single) 473ml	Beer	3.38	0	\N	\N	2026-01-08 14:42:27.824195	2.37	35.00	0.10	0.00	f	Corona (single) beer - 473ml can
1048	Moose Jaw Brewing 12-pack	Craft Beer	96.90	0	\N	\N	2026-01-08 14:42:27.824195	67.83	35.00	1.20	0.00	f	Moose Jaw Brewing craft beer - 12-pack
1049	Strongbow 6-pack	Ciders	24.38	0	\N	\N	2026-01-08 14:42:27.824195	17.07	35.00	0.60	0.00	f	Strongbow cider - 6-pack
1054	Barefoot Riesling 1L	Wine - White	22.21	0	\N	\N	2026-01-08 14:43:00.529192	15.55	35.00	0.10	0.00	f	Barefoot Riesling white wine - 1L
1055	Barefoot Sauvignon Blanc 1L	Wine - White	22.21	0	\N	\N	2026-01-08 14:43:00.529192	15.55	35.00	0.10	0.00	f	Barefoot Sauvignon Blanc white wine - 1L
1057	Fiddlehead 1L	Wine - White	20.39	0	\N	\N	2026-01-08 14:43:00.529192	14.27	35.00	0.10	0.00	f	Fiddlehead white wine - 1L
1058	Kendall Jackson Chardonnay 1L	Wine - White	21.76	0	\N	\N	2026-01-08 14:43:00.529192	15.23	35.00	0.10	0.00	f	Kendall Jackson Chardonnay white wine - 1L
1059	Saint Clair Sauvignon 1L	Wine - White	21.63	0	\N	\N	2026-01-08 14:43:00.529192	15.14	35.00	0.10	0.00	f	Saint Clair Sauvignon white wine - 1L
1060	Belgian Ale (single) 6-pack	Beer	13.72	0	\N	\N	2026-01-08 14:43:21.051986	9.60	35.00	0.60	0.00	f	Belgian Ale (single) beer - 6-pack
1061	Belgian Ale (single) 12-pack	Beer	25.91	0	\N	\N	2026-01-08 14:43:21.051986	18.14	35.00	1.20	0.00	f	Belgian Ale (single) beer - 12-pack
1062	Bud Light Seltzer 6-pack	Hard Seltzers	32.40	0	\N	\N	2026-01-08 14:43:21.051986	22.68	35.00	0.60	0.00	f	Bud Light Seltzer seltzer - 6-pack
1063	Bud Light Seltzer 12-pack	Hard Seltzers	61.20	0	\N	\N	2026-01-08 14:43:21.051986	42.84	35.00	1.20	0.00	f	Bud Light Seltzer seltzer - 12-pack
1064	Ace 12-pack	Ciders	38.25	0	\N	\N	2026-01-08 14:43:21.051986	26.78	35.00	1.20	0.00	f	Ace cider - 12-pack
38	Red Bull Red Bull	Energy	5.00	50	\N	/data/product_images/38_Red_Bull_Red_Bull.jpg	2026-01-07 18:15:08.023848	3.70	35.00	0.10	0.00	f	\N
771	Tecate 50ml	Tequila	3.80	50	\N	/data/product_images/771_Tecate_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
772	Tecate 375ml	Tequila	20.90	50	\N	/data/product_images/772_Tecate_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
773	Tecate 750ml	Tequila	38.00	50	\N	/data/product_images/773_Tecate_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
774	Tecate 1L	Tequila	47.50	50	\N	/data/product_images/774_Tecate_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
775	Tecate 1.75L	Tequila	76.00	50	\N	/data/product_images/775_Tecate_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
776	Kahlúa 50ml	Liqueurs	3.50	50	\N	/data/product_images/776_Kahlúa_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
777	Kahlúa 375ml	Liqueurs	19.25	50	\N	/data/product_images/777_Kahlúa_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
778	Kahlúa 750ml	Liqueurs	35.00	50	\N	/data/product_images/778_Kahlúa_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
779	Kahlúa 1L	Liqueurs	43.75	50	\N	/data/product_images/779_Kahlúa_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
77	Jim Beam 375ml	Whiskey	18.03	50	\N	/data/product_images/77_Jim_Beam_375ml.jpg	2026-01-07 18:24:49.609209	13.36	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
780	Kahlúa 1.75L	Liqueurs	70.00	50	\N	/data/product_images/780_Kahlúa_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
781	Baileys Irish Cream 50ml	Liqueurs	3.50	50	\N	/data/product_images/781_Baileys_Irish_Cream_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
782	Baileys Irish Cream 375ml	Liqueurs	19.25	50	\N	/data/product_images/782_Baileys_Irish_Cream_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
783	Baileys Irish Cream 750ml	Liqueurs	35.00	50	\N	/data/product_images/783_Baileys_Irish_Cream_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
784	Baileys Irish Cream 1L	Liqueurs	43.75	50	\N	/data/product_images/784_Baileys_Irish_Cream_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
785	Baileys Irish Cream 1.75L	Liqueurs	70.00	50	\N	/data/product_images/785_Baileys_Irish_Cream_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
78	Jim Beam 750ml	Whiskey	30.57	50	\N	/data/product_images/78_Jim_Beam_750ml.jpg	2026-01-07 18:24:49.609209	22.64	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
791	Grand Marnier 50ml	Liqueurs	3.50	50	\N	/data/product_images/791_Grand_Marnier_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
792	Grand Marnier 375ml	Liqueurs	19.25	50	\N	/data/product_images/792_Grand_Marnier_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
1066	Non-Alcoholic Sparkling Wine 750ml	Non-Alcoholic	15.99	100	\N	\N	2026-01-08 15:43:19.424246	11.19	35.00	0.10	0.00	t	Alcohol-free sparkling celebration wine
793	Grand Marnier 750ml	Liqueurs	35.00	50	\N	/data/product_images/793_Grand_Marnier_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
794	Grand Marnier 1L	Liqueurs	43.75	50	\N	/data/product_images/794_Grand_Marnier_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
795	Grand Marnier 1.75L	Liqueurs	70.00	50	\N	/data/product_images/795_Grand_Marnier_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
796	Amaretto 50ml	Liqueurs	3.50	50	\N	/data/product_images/796_Amaretto_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
1000	Woodchuck 473ml	Ciders	4.88	50	\N	/data/product_images/1000_Woodchuck_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1067	Martinelli's Sparkling Cider 750ml	Non-Alcoholic	18.99	100	\N	\N	2026-01-08 15:43:19.424246	13.29	35.00	0.10	0.00	t	Non-alcoholic sparkling apple cider - perfect for celebrations
1001	Woodchuck 24-pack	Ciders	180.00	50	\N	/data/product_images/1001_Woodchuck_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
1002	Angry Orchard 355ml	Ciders	3.75	50	\N	/data/product_images/1002_Angry_Orchard_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1003	Angry Orchard 473ml	Ciders	4.88	50	\N	/data/product_images/1003_Angry_Orchard_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1004	Angry Orchard 24-pack	Ciders	180.00	50	\N	/data/product_images/1004_Angry_Orchard_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
1005	Magners 355ml	Ciders	3.75	50	\N	/data/product_images/1005_Magners_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1006	Magners 473ml	Ciders	4.88	50	\N	/data/product_images/1006_Magners_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1007	Magners 24-pack	Ciders	180.00	50	\N	/data/product_images/1007_Magners_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
1008	Bulmers 355ml	Ciders	3.75	50	\N	/data/product_images/1008_Bulmers_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1009	Bulmers 473ml	Ciders	4.88	50	\N	/data/product_images/1009_Bulmers_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1010	Bulmers 24-pack	Ciders	180.00	50	\N	/data/product_images/1010_Bulmers_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
1011	Ciderboys 355ml	Ciders	3.75	50	\N	/data/product_images/1011_Ciderboys_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1012	Ciderboys 473ml	Ciders	4.88	50	\N	/data/product_images/1012_Ciderboys_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1013	Ciderboys 24-pack	Ciders	180.00	50	\N	/data/product_images/1013_Ciderboys_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
1014	Stella Artois Cidre 355ml	Ciders	3.75	50	\N	/data/product_images/1014_Stella_Artois_Cidre_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Belgian lager. Smooth, balanced, slightly fruity.
1015	Stella Artois Cidre 473ml	Ciders	4.88	50	\N	/data/product_images/1015_Stella_Artois_Cidre_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Belgian lager. Smooth, balanced, slightly fruity.
1016	Stella Artois Cidre 24-pack	Ciders	180.00	50	\N	/data/product_images/1016_Stella_Artois_Cidre_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Belgian lager. Smooth, balanced, slightly fruity.
1017	Blake's Hard Cider 355ml	Ciders	3.75	50	\N	/data/product_images/1017_Blake's_Hard_Cider_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1018	Blake's Hard Cider 473ml	Ciders	4.88	50	\N	/data/product_images/1018_Blake's_Hard_Cider_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1019	Blake's Hard Cider 24-pack	Ciders	180.00	50	\N	/data/product_images/1019_Blake's_Hard_Cider_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
164	Grey Goose 1L	Vodka	37.32	50	\N	/data/product_images/164_Grey_Goose_1L.jpg	2026-01-07 18:24:49.614561	27.64	35.00	0.10	0.00	f	French vodka distilled from Picardy wheat. Smooth, crisp, iconic.
165	Grey Goose 1.75L	Vodka	59.98	50	\N	/data/product_images/165_Grey_Goose_1.75L.jpg	2026-01-07 18:24:49.614561	44.43	35.00	0.25	0.00	f	French vodka distilled from Picardy wheat. Smooth, crisp, iconic.
166	Ketel One 50ml	Vodka	2.90	50	\N	/data/product_images/166_Ketel_One_50ml.jpg	2026-01-07 18:24:49.614561	2.15	35.00	0.10	0.00	f	Dutch vodka with traditional copper pot still distillation. Light and clean.
167	Ketel One 375ml	Vodka	16.47	50	\N	/data/product_images/167_Ketel_One_375ml.jpg	2026-01-07 18:24:49.614561	12.20	35.00	0.10	0.00	f	Dutch vodka with traditional copper pot still distillation. Light and clean.
168	Ketel One 750ml	Vodka	28.76	50	\N	/data/product_images/168_Ketel_One_750ml.jpg	2026-01-07 18:24:49.614561	21.30	35.00	0.10	0.00	f	Dutch vodka with traditional copper pot still distillation. Light and clean.
169	Ketel One 1L	Vodka	36.23	50	\N	/data/product_images/169_Ketel_One_1L.jpg	2026-01-07 18:24:49.614561	26.84	35.00	0.10	0.00	f	Dutch vodka with traditional copper pot still distillation. Light and clean.
170	Ketel One 1.75L	Vodka	57.85	50	\N	/data/product_images/170_Ketel_One_1.75L.jpg	2026-01-07 18:24:49.614561	42.85	35.00	0.25	0.00	f	Dutch vodka with traditional copper pot still distillation. Light and clean.
190	Skyy 1.75L	Vodka	60.37	50	\N	/data/product_images/190_Skyy_1.75L.jpg	2026-01-07 18:24:49.614561	44.72	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
191	Belvedere 50ml	Vodka	3.13	50	\N	/data/product_images/191_Belvedere_50ml.jpg	2026-01-07 18:24:49.614561	2.32	35.00	0.10	0.00	f	Ultra-premium Polish vodka from rye. Smooth and silky with subtle grain character.
192	Belvedere 375ml	Vodka	16.54	50	\N	/data/product_images/192_Belvedere_375ml.jpg	2026-01-07 18:24:49.614561	12.25	35.00	0.10	0.00	f	Ultra-premium Polish vodka from rye. Smooth and silky with subtle grain character.
193	Belvedere 750ml	Vodka	29.78	50	\N	/data/product_images/193_Belvedere_750ml.jpg	2026-01-07 18:24:49.614561	22.06	35.00	0.10	0.00	f	Ultra-premium Polish vodka from rye. Smooth and silky with subtle grain character.
194	Belvedere 1L	Vodka	36.55	50	\N	/data/product_images/194_Belvedere_1L.jpg	2026-01-07 18:24:49.614561	27.07	35.00	0.10	0.00	f	Ultra-premium Polish vodka from rye. Smooth and silky with subtle grain character.
195	Belvedere 1.75L	Vodka	59.38	50	\N	/data/product_images/195_Belvedere_1.75L.jpg	2026-01-07 18:24:49.614561	43.99	35.00	0.25	0.00	f	Ultra-premium Polish vodka from rye. Smooth and silky with subtle grain character.
196	Stolichnaya 50ml	Vodka	2.91	50	\N	/data/product_images/196_Stolichnaya_50ml.jpg	2026-01-07 18:24:49.614561	2.16	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
197	Stolichnaya 375ml	Vodka	16.40	50	\N	/data/product_images/197_Stolichnaya_375ml.jpg	2026-01-07 18:24:49.614561	12.15	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
1065	Baby Duck Sparkling Wine 1.5L	Champagne	23.99	100	\N	\N	2026-01-08 15:43:19.424246	16.79	35.00	0.10	0.00	t	Classic Canadian sparkling wine - sweet and fruity (1.5L magnum)
198	Stolichnaya 750ml	Vodka	31.35	50	\N	/data/product_images/198_Stolichnaya_750ml.jpg	2026-01-07 18:24:49.614561	23.22	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
199	Stolichnaya 1L	Vodka	38.48	50	\N	/data/product_images/199_Stolichnaya_1L.jpg	2026-01-07 18:24:49.614561	28.50	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
200	Stolichnaya 1.75L	Vodka	62.20	50	\N	/data/product_images/200_Stolichnaya_1.75L.jpg	2026-01-07 18:24:49.614561	46.07	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
201	Tanqueray 50ml	Vodka	2.94	50	\N	/data/product_images/201_Tanqueray_50ml.jpg	2026-01-07 18:24:49.614561	2.18	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
202	Tanqueray 375ml	Vodka	15.89	50	\N	/data/product_images/202_Tanqueray_375ml.jpg	2026-01-07 18:24:49.614561	11.77	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
203	Tanqueray 750ml	Vodka	30.17	50	\N	/data/product_images/203_Tanqueray_750ml.jpg	2026-01-07 18:24:49.614561	22.35	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
204	Tanqueray 1L	Vodka	36.66	50	\N	/data/product_images/204_Tanqueray_1L.jpg	2026-01-07 18:24:49.614561	27.16	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
205	Tanqueray 1.75L	Vodka	61.55	50	\N	/data/product_images/205_Tanqueray_1.75L.jpg	2026-01-07 18:24:49.614561	45.59	35.00	0.25	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
206	Ruskova 50ml	Vodka	2.88	50	\N	/data/product_images/206_Ruskova_50ml.jpg	2026-01-07 18:24:49.614561	2.13	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
207	Ruskova 375ml	Vodka	16.22	50	\N	/data/product_images/207_Ruskova_375ml.jpg	2026-01-07 18:24:49.614561	12.01	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
208	Ruskova 750ml	Vodka	30.96	50	\N	/data/product_images/208_Ruskova_750ml.jpg	2026-01-07 18:24:49.614561	22.93	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
209	Ruskova 1L	Vodka	37.58	50	\N	/data/product_images/209_Ruskova_1L.jpg	2026-01-07 18:24:49.614561	27.84	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
210	Ruskova 1.75L	Vodka	58.23	50	\N	/data/product_images/210_Ruskova_1.75L.jpg	2026-01-07 18:24:49.614561	43.13	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
211	Bacardi 50ml	Rum	2.75	50	\N	/data/product_images/211_Bacardi_50ml.jpg	2026-01-07 18:24:49.618189	2.04	35.00	0.10	0.00	f	White rum, light and crisp. Perfect base for mojitos and daiquiris.
212	Bacardi 375ml	Rum	14.21	50	\N	/data/product_images/212_Bacardi_375ml.jpg	2026-01-07 18:24:49.618189	10.53	35.00	0.10	0.00	f	White rum, light and crisp. Perfect base for mojitos and daiquiris.
213	Bacardi 750ml	Rum	27.23	50	\N	/data/product_images/213_Bacardi_750ml.jpg	2026-01-07 18:24:49.618189	20.17	35.00	0.10	0.00	f	White rum, light and crisp. Perfect base for mojitos and daiquiris.
214	Bacardi 1L	Rum	33.54	50	\N	/data/product_images/214_Bacardi_1L.jpg	2026-01-07 18:24:49.618189	24.84	35.00	0.10	0.00	f	White rum, light and crisp. Perfect base for mojitos and daiquiris.
215	Bacardi 1.75L	Rum	55.11	50	\N	/data/product_images/215_Bacardi_1.75L.jpg	2026-01-07 18:24:49.618189	40.82	35.00	0.25	0.00	f	White rum, light and crisp. Perfect base for mojitos and daiquiris.
216	Captain Morgan 50ml	Rum	2.73	50	\N	/data/product_images/216_Captain_Morgan_50ml.jpg	2026-01-07 18:24:49.618189	2.02	35.00	0.10	0.00	f	Dark spiced rum with vanilla and cinnamon notes. Great for rum-cola.
217	Captain Morgan 375ml	Rum	15.33	50	\N	/data/product_images/217_Captain_Morgan_375ml.jpg	2026-01-07 18:24:49.618189	11.36	35.00	0.10	0.00	f	Dark spiced rum with vanilla and cinnamon notes. Great for rum-cola.
230	Mount Gay 1.75L	Rum	56.07	50	\N	/data/product_images/230_Mount_Gay_1.75L.jpg	2026-01-07 18:24:49.618189	41.53	35.00	0.25	0.00	f	Premium rum from Barbados. Full-bodied with vanilla and oak.
241	Appleton Estate 50ml	Rum	2.75	50	\N	/data/product_images/241_Appleton_Estate_50ml.jpg	2026-01-07 18:24:49.618189	2.04	35.00	0.10	0.00	f	Jamaican rum with fruity, complex profile. Excellent aged expression.
242	Appleton Estate 375ml	Rum	15.38	50	\N	/data/product_images/242_Appleton_Estate_375ml.jpg	2026-01-07 18:24:49.618189	11.39	35.00	0.10	0.00	f	Jamaican rum with fruity, complex profile. Excellent aged expression.
243	Appleton Estate 750ml	Rum	26.38	50	\N	/data/product_images/243_Appleton_Estate_750ml.jpg	2026-01-07 18:24:49.618189	19.54	35.00	0.10	0.00	f	Jamaican rum with fruity, complex profile. Excellent aged expression.
244	Appleton Estate 1L	Rum	35.00	50	\N	/data/product_images/244_Appleton_Estate_1L.jpg	2026-01-07 18:24:49.618189	25.93	35.00	0.10	0.00	f	Jamaican rum with fruity, complex profile. Excellent aged expression.
245	Appleton Estate 1.75L	Rum	53.59	50	\N	/data/product_images/245_Appleton_Estate_1.75L.jpg	2026-01-07 18:24:49.618189	39.70	35.00	0.25	0.00	f	Jamaican rum with fruity, complex profile. Excellent aged expression.
246	Havana Club 50ml	Rum	2.58	50	\N	/data/product_images/246_Havana_Club_50ml.jpg	2026-01-07 18:24:49.618189	1.91	35.00	0.10	0.00	f	Cuban rum with complex caramel notes. Smooth aging process.
247	Havana Club 375ml	Rum	14.80	50	\N	/data/product_images/247_Havana_Club_375ml.jpg	2026-01-07 18:24:49.618189	10.96	35.00	0.10	0.00	f	Cuban rum with complex caramel notes. Smooth aging process.
248	Havana Club 750ml	Rum	26.82	50	\N	/data/product_images/248_Havana_Club_750ml.jpg	2026-01-07 18:24:49.618189	19.87	35.00	0.10	0.00	f	Cuban rum with complex caramel notes. Smooth aging process.
249	Havana Club 1L	Rum	33.66	50	\N	/data/product_images/249_Havana_Club_1L.jpg	2026-01-07 18:24:49.618189	24.93	35.00	0.10	0.00	f	Cuban rum with complex caramel notes. Smooth aging process.
250	Havana Club 1.75L	Rum	55.62	50	\N	/data/product_images/250_Havana_Club_1.75L.jpg	2026-01-07 18:24:49.618189	41.20	35.00	0.25	0.00	f	Cuban rum with complex caramel notes. Smooth aging process.
251	Diplo 50ml	Rum	2.69	50	\N	/data/product_images/251_Diplo_50ml.jpg	2026-01-07 18:24:49.618189	1.99	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
252	Diplo 375ml	Rum	14.95	50	\N	/data/product_images/252_Diplo_375ml.jpg	2026-01-07 18:24:49.618189	11.07	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
253	Diplo 750ml	Rum	26.10	50	\N	/data/product_images/253_Diplo_750ml.jpg	2026-01-07 18:24:49.618189	19.33	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
45	Hennessy Hennessy Cognac	Spirits	80.00	50	\N	/data/product_images/45_Hennessy_Hennessy_Cognac.jpg	2026-01-07 18:15:08.023848	59.26	35.00	0.10	0.00	f	Premium Cognac. Rich, complex, elegant.
1068	Baby Duck Sparkling Wine 750ml	Champagne	12.99	100	\N	\N	2026-01-08 15:57:41.749957	9.09	35.00	0.10	0.00	t	Classic Canadian sparkling wine - sweet and fruity
100	Jameson 1.75L	Whiskey	62.29	50	\N	/data/product_images/100_Jameson_1.75L.jpg	2026-01-07 18:24:49.609209	46.14	35.00	0.25	0.00	f	Irish whiskey with triple distillation. Smooth, sweet, triple pot still character.
101	Bulleit 50ml	Whiskey	3.17	50	\N	/data/product_images/101_Bulleit_50ml.jpg	2026-01-07 18:24:49.609209	2.35	35.00	0.10	0.00	f	Kentucky straight bourbon. High rye content gives spicy finish.
254	Diplo 1L	Rum	34.28	50	\N	/data/product_images/254_Diplo_1L.jpg	2026-01-07 18:24:49.618189	25.39	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
255	Diplo 1.75L	Rum	53.01	50	\N	/data/product_images/255_Diplo_1.75L.jpg	2026-01-07 18:24:49.618189	39.27	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
260	Plantation 1.75L	Rum	53.74	50	\N	/data/product_images/260_Plantation_1.75L.jpg	2026-01-07 18:24:49.618189	39.81	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
266	Bombay Sapphire 50ml	Gin	3.35	50	\N	/data/product_images/266_Bombay_Sapphire_50ml.jpg	2026-01-07 18:24:49.623297	2.48	35.00	0.10	0.00	f	Gin distilled with 10 botanicals. Crisp, balanced profile.
267	Bombay Sapphire 375ml	Gin	18.39	50	\N	/data/product_images/267_Bombay_Sapphire_375ml.jpg	2026-01-07 18:24:49.623297	13.62	35.00	0.10	0.00	f	Gin distilled with 10 botanicals. Crisp, balanced profile.
268	Bombay Sapphire 750ml	Gin	32.66	50	\N	/data/product_images/268_Bombay_Sapphire_750ml.jpg	2026-01-07 18:24:49.623297	24.19	35.00	0.10	0.00	f	Gin distilled with 10 botanicals. Crisp, balanced profile.
269	Bombay Sapphire 1L	Gin	38.92	50	\N	/data/product_images/269_Bombay_Sapphire_1L.jpg	2026-01-07 18:24:49.623297	28.83	35.00	0.10	0.00	f	Gin distilled with 10 botanicals. Crisp, balanced profile.
270	Bombay Sapphire 1.75L	Gin	63.68	50	\N	/data/product_images/270_Bombay_Sapphire_1.75L.jpg	2026-01-07 18:24:49.623297	47.17	35.00	0.25	0.00	f	Gin distilled with 10 botanicals. Crisp, balanced profile.
271	Hendrick's 50ml	Gin	3.16	50	\N	/data/product_images/271_Hendrick's_50ml.jpg	2026-01-07 18:24:49.623297	2.34	35.00	0.10	0.00	f	Scottish gin infused with cucumber. Unique, refreshing, smooth.
272	Hendrick's 375ml	Gin	17.23	50	\N	/data/product_images/272_Hendrick's_375ml.jpg	2026-01-07 18:24:49.623297	12.76	35.00	0.10	0.00	f	Scottish gin infused with cucumber. Unique, refreshing, smooth.
273	Hendrick's 750ml	Gin	32.41	50	\N	/data/product_images/273_Hendrick's_750ml.jpg	2026-01-07 18:24:49.623297	24.01	35.00	0.10	0.00	f	Scottish gin infused with cucumber. Unique, refreshing, smooth.
274	Hendrick's 1L	Gin	41.43	50	\N	/data/product_images/274_Hendrick's_1L.jpg	2026-01-07 18:24:49.623297	30.69	35.00	0.10	0.00	f	Scottish gin infused with cucumber. Unique, refreshing, smooth.
275	Hendrick's 1.75L	Gin	62.92	50	\N	/data/product_images/275_Hendrick's_1.75L.jpg	2026-01-07 18:24:49.623297	46.61	35.00	0.25	0.00	f	Scottish gin infused with cucumber. Unique, refreshing, smooth.
276	Beefeater 50ml	Gin	3.23	50	\N	/data/product_images/276_Beefeater_50ml.jpg	2026-01-07 18:24:49.623297	2.39	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
1069	Prosecco 187ml (mini)	Champagne	6.99	100	\N	\N	2026-01-08 16:11:43.045748	4.89	35.00	0.10	0.00	t	Italian sparkling wine - dry and refreshing (mini bottle)
1070	Prosecco 750ml	Champagne	16.99	100	\N	\N	2026-01-08 16:11:43.045748	11.89	35.00	0.10	0.00	t	Italian sparkling wine - dry and refreshing
1071	Prosecco 1.5L	Champagne	29.99	100	\N	\N	2026-01-08 16:11:43.045748	20.99	35.00	0.10	0.00	t	Italian sparkling wine - dry and refreshing (magnum)
277	Beefeater 375ml	Gin	17.05	50	\N	/data/product_images/277_Beefeater_375ml.jpg	2026-01-07 18:24:49.623297	12.63	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
278	Beefeater 750ml	Gin	33.32	50	\N	/data/product_images/278_Beefeater_750ml.jpg	2026-01-07 18:24:49.623297	24.68	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
279	Beefeater 1L	Gin	40.53	50	\N	/data/product_images/279_Beefeater_1L.jpg	2026-01-07 18:24:49.623297	30.02	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
280	Beefeater 1.75L	Gin	65.60	50	\N	/data/product_images/280_Beefeater_1.75L.jpg	2026-01-07 18:24:49.623297	48.59	35.00	0.25	0.00	f	London dry gin with prominent juniper and orange peel.
281	Jägermeister 50ml	Gin	3.06	50	\N	/data/product_images/281_Jägermeister_50ml.jpg	2026-01-07 18:24:49.623297	2.27	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
282	Jägermeister 375ml	Gin	18.07	50	\N	/data/product_images/282_Jägermeister_375ml.jpg	2026-01-07 18:24:49.623297	13.39	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
283	Jägermeister 750ml	Gin	31.67	50	\N	/data/product_images/283_Jägermeister_750ml.jpg	2026-01-07 18:24:49.623297	23.46	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
284	Jägermeister 1L	Gin	41.70	50	\N	/data/product_images/284_Jägermeister_1L.jpg	2026-01-07 18:24:49.623297	30.89	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
285	Jägermeister 1.75L	Gin	61.98	50	\N	/data/product_images/285_Jägermeister_1.75L.jpg	2026-01-07 18:24:49.623297	45.91	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
286	Seagram's 50ml	Gin	3.15	50	\N	/data/product_images/286_Seagram's_50ml.jpg	2026-01-07 18:24:49.623297	2.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
287	Seagram's 375ml	Gin	18.28	50	\N	/data/product_images/287_Seagram's_375ml.jpg	2026-01-07 18:24:49.623297	13.54	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
288	Seagram's 750ml	Gin	33.38	50	\N	/data/product_images/288_Seagram's_750ml.jpg	2026-01-07 18:24:49.623297	24.73	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
289	Seagram's 1L	Gin	39.23	50	\N	/data/product_images/289_Seagram's_1L.jpg	2026-01-07 18:24:49.623297	29.06	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
290	Seagram's 1.75L	Gin	61.41	50	\N	/data/product_images/290_Seagram's_1.75L.jpg	2026-01-07 18:24:49.623297	45.49	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
1041	San Pellegrino Aranciata Orange	Soft Drinks	2.99	\N	\N	\N	2026-01-08 14:36:42.348195	2.09	35.00	0.10	0.00	f	Italian blood orange soda
1026	Apothic Red 750ml	Wine - Red	18.99	\N	\N	\N	2026-01-08 14:36:42.348195	13.29	35.00	0.10	0.00	f	Red blend with berry and spice notes
102	Bulleit 375ml	Whiskey	18.04	50	\N	/data/product_images/102_Bulleit_375ml.jpg	2026-01-07 18:24:49.609209	13.36	35.00	0.10	0.00	f	Kentucky straight bourbon. High rye content gives spicy finish.
103	Bulleit 750ml	Whiskey	32.97	50	\N	/data/product_images/103_Bulleit_750ml.jpg	2026-01-07 18:24:49.609209	24.42	35.00	0.10	0.00	f	Kentucky straight bourbon. High rye content gives spicy finish.
104	Bulleit 1L	Whiskey	41.12	50	\N	/data/product_images/104_Bulleit_1L.jpg	2026-01-07 18:24:49.609209	30.46	35.00	0.10	0.00	f	Kentucky straight bourbon. High rye content gives spicy finish.
105	Bulleit 1.75L	Whiskey	65.53	50	\N	/data/product_images/105_Bulleit_1.75L.jpg	2026-01-07 18:24:49.609209	48.54	35.00	0.25	0.00	f	Kentucky straight bourbon. High rye content gives spicy finish.
108	Maker's Mark 750ml	Whiskey	30.73	50	\N	/data/product_images/108_Maker's_Mark_750ml.jpg	2026-01-07 18:24:49.609209	22.76	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
109	Maker's Mark 1L	Whiskey	40.93	50	\N	/data/product_images/109_Maker's_Mark_1L.jpg	2026-01-07 18:24:49.609209	30.32	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
256	Plantation 50ml	Rum	2.59	50	\N	/data/product_images/256_Plantation_50ml.jpg	2026-01-07 18:24:49.618189	1.92	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
257	Plantation 375ml	Rum	14.37	50	\N	/data/product_images/257_Plantation_375ml.jpg	2026-01-07 18:24:49.618189	10.64	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
258	Plantation 750ml	Rum	26.60	50	\N	/data/product_images/258_Plantation_750ml.jpg	2026-01-07 18:24:49.618189	19.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
259	Plantation 1L	Rum	34.65	50	\N	/data/product_images/259_Plantation_1L.jpg	2026-01-07 18:24:49.618189	25.67	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
291	Gordons 50ml	Gin	3.16	50	\N	/data/product_images/291_Gordons_50ml.jpg	2026-01-07 18:24:49.623297	2.34	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
292	Gordons 375ml	Gin	17.07	50	\N	/data/product_images/292_Gordons_375ml.jpg	2026-01-07 18:24:49.623297	12.64	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
293	Gordons 750ml	Gin	33.04	50	\N	/data/product_images/293_Gordons_750ml.jpg	2026-01-07 18:24:49.623297	24.47	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
294	Gordons 1L	Gin	39.28	50	\N	/data/product_images/294_Gordons_1L.jpg	2026-01-07 18:24:49.623297	29.10	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
295	Gordons 1.75L	Gin	62.84	50	\N	/data/product_images/295_Gordons_1.75L.jpg	2026-01-07 18:24:49.623297	46.55	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
296	Botanist 50ml	Gin	3.16	50	\N	/data/product_images/296_Botanist_50ml.jpg	2026-01-07 18:24:49.623297	2.34	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
297	Botanist 375ml	Gin	17.71	50	\N	/data/product_images/297_Botanist_375ml.jpg	2026-01-07 18:24:49.623297	13.12	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
298	Botanist 750ml	Gin	30.89	50	\N	/data/product_images/298_Botanist_750ml.jpg	2026-01-07 18:24:49.623297	22.88	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
299	Botanist 1L	Gin	40.08	50	\N	/data/product_images/299_Botanist_1L.jpg	2026-01-07 18:24:49.623297	29.69	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
300	Botanist 1.75L	Gin	63.97	50	\N	/data/product_images/300_Botanist_1.75L.jpg	2026-01-07 18:24:49.623297	47.39	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
301	Jose Cuervo 50ml	Tequila	3.67	50	\N	/data/product_images/301_Jose_Cuervo_50ml.jpg	2026-01-07 18:24:49.626279	2.72	35.00	0.10	0.00	f	Classic tequila. Smooth, versatile for margaritas.
302	Jose Cuervo 375ml	Tequila	18.64	50	\N	/data/product_images/302_Jose_Cuervo_375ml.jpg	2026-01-07 18:24:49.626279	13.81	35.00	0.10	0.00	f	Classic tequila. Smooth, versatile for margaritas.
303	Jose Cuervo 750ml	Tequila	35.39	50	\N	/data/product_images/303_Jose_Cuervo_750ml.jpg	2026-01-07 18:24:49.626279	26.21	35.00	0.10	0.00	f	Classic tequila. Smooth, versatile for margaritas.
304	Jose Cuervo 1L	Tequila	42.43	50	\N	/data/product_images/304_Jose_Cuervo_1L.jpg	2026-01-07 18:24:49.626279	31.43	35.00	0.10	0.00	f	Classic tequila. Smooth, versatile for margaritas.
305	Jose Cuervo 1.75L	Tequila	67.08	50	\N	/data/product_images/305_Jose_Cuervo_1.75L.jpg	2026-01-07 18:24:49.626279	49.69	35.00	0.25	0.00	f	Classic tequila. Smooth, versatile for margaritas.
110	Maker's Mark 1.75L	Whiskey	66.06	50	\N	/data/product_images/110_Maker's_Mark_1.75L.jpg	2026-01-07 18:24:49.609209	48.93	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
111	Buffalo Trace 50ml	Whiskey	3.08	50	\N	/data/product_images/111_Buffalo_Trace_50ml.jpg	2026-01-07 18:24:49.609209	2.28	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
112	Buffalo Trace 375ml	Whiskey	17.84	50	\N	/data/product_images/112_Buffalo_Trace_375ml.jpg	2026-01-07 18:24:49.609209	13.21	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
113	Buffalo Trace 750ml	Whiskey	32.19	50	\N	/data/product_images/113_Buffalo_Trace_750ml.jpg	2026-01-07 18:24:49.609209	23.84	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
114	Buffalo Trace 1L	Whiskey	39.99	50	\N	/data/product_images/114_Buffalo_Trace_1L.jpg	2026-01-07 18:24:49.609209	29.62	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
115	Buffalo Trace 1.75L	Whiskey	65.41	50	\N	/data/product_images/115_Buffalo_Trace_1.75L.jpg	2026-01-07 18:24:49.609209	48.45	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
116	Wild Turkey 50ml	Whiskey	3.30	50	\N	/data/product_images/116_Wild_Turkey_50ml.jpg	2026-01-07 18:24:49.609209	2.44	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
117	Wild Turkey 375ml	Whiskey	17.66	50	\N	/data/product_images/117_Wild_Turkey_375ml.jpg	2026-01-07 18:24:49.609209	13.08	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
118	Wild Turkey 750ml	Whiskey	31.35	50	\N	/data/product_images/118_Wild_Turkey_750ml.jpg	2026-01-07 18:24:49.609209	23.22	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
119	Wild Turkey 1L	Whiskey	41.79	50	\N	/data/product_images/119_Wild_Turkey_1L.jpg	2026-01-07 18:24:49.609209	30.96	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
120	Wild Turkey 1.75L	Whiskey	65.20	50	\N	/data/product_images/120_Wild_Turkey_1.75L.jpg	2026-01-07 18:24:49.609209	48.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
306	Patrón 50ml	Tequila	3.53	50	\N	/data/product_images/306_Patrón_50ml.jpg	2026-01-07 18:24:49.626279	2.61	35.00	0.10	0.00	f	Premium silver tequila. Smooth, crisp, clean finish.
307	Patrón 375ml	Tequila	19.41	50	\N	/data/product_images/307_Patrón_375ml.jpg	2026-01-07 18:24:49.626279	14.38	35.00	0.10	0.00	f	Premium silver tequila. Smooth, crisp, clean finish.
308	Patrón 750ml	Tequila	36.28	50	\N	/data/product_images/308_Patrón_750ml.jpg	2026-01-07 18:24:49.626279	26.87	35.00	0.10	0.00	f	Premium silver tequila. Smooth, crisp, clean finish.
309	Patrón 1L	Tequila	42.69	50	\N	/data/product_images/309_Patrón_1L.jpg	2026-01-07 18:24:49.626279	31.62	35.00	0.10	0.00	f	Premium silver tequila. Smooth, crisp, clean finish.
310	Patrón 1.75L	Tequila	71.79	50	\N	/data/product_images/310_Patrón_1.75L.jpg	2026-01-07 18:24:49.626279	53.18	35.00	0.25	0.00	f	Premium silver tequila. Smooth, crisp, clean finish.
311	El Tesoro 50ml	Tequila	3.54	50	\N	/data/product_images/311_El_Tesoro_50ml.jpg	2026-01-07 18:24:49.626279	2.62	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
312	El Tesoro 375ml	Tequila	19.22	50	\N	/data/product_images/312_El_Tesoro_375ml.jpg	2026-01-07 18:24:49.626279	14.24	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
313	El Tesoro 750ml	Tequila	33.89	50	\N	/data/product_images/313_El_Tesoro_750ml.jpg	2026-01-07 18:24:49.626279	25.10	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
314	El Tesoro 1L	Tequila	45.89	50	\N	/data/product_images/314_El_Tesoro_1L.jpg	2026-01-07 18:24:49.626279	33.99	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
315	El Tesoro 1.75L	Tequila	69.63	50	\N	/data/product_images/315_El_Tesoro_1.75L.jpg	2026-01-07 18:24:49.626279	51.58	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
316	Don Julio 50ml	Tequila	3.53	50	\N	/data/product_images/316_Don_Julio_50ml.jpg	2026-01-07 18:24:49.626279	2.61	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
317	Don Julio 375ml	Tequila	19.71	50	\N	/data/product_images/317_Don_Julio_375ml.jpg	2026-01-07 18:24:49.626279	14.60	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
332	Sauza 375ml	Tequila	19.96	50	\N	/data/product_images/332_Sauza_375ml.jpg	2026-01-07 18:24:49.626279	14.79	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
337	Tres Generaciones 375ml	Tequila	18.87	50	\N	/data/product_images/337_Tres_Generaciones_375ml.jpg	2026-01-07 18:24:49.626279	13.98	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
338	Tres Generaciones 750ml	Tequila	34.81	50	\N	/data/product_images/338_Tres_Generaciones_750ml.jpg	2026-01-07 18:24:49.626279	25.79	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
339	Tres Generaciones 1L	Tequila	43.37	50	\N	/data/product_images/339_Tres_Generaciones_1L.jpg	2026-01-07 18:24:49.626279	32.13	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
340	Tres Generaciones 1.75L	Tequila	70.03	50	\N	/data/product_images/340_Tres_Generaciones_1.75L.jpg	2026-01-07 18:24:49.626279	51.87	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
121	Woodford Reserve 50ml	Whiskey	3.25	50	\N	/data/product_images/121_Woodford_Reserve_50ml.jpg	2026-01-07 18:24:49.609209	2.41	35.00	0.10	0.00	f	Premium Kentucky bourbon. Complex spice and fruit notes.
122	Woodford Reserve 375ml	Whiskey	18.11	50	\N	/data/product_images/122_Woodford_Reserve_375ml.jpg	2026-01-07 18:24:49.609209	13.41	35.00	0.10	0.00	f	Premium Kentucky bourbon. Complex spice and fruit notes.
123	Woodford Reserve 750ml	Whiskey	31.07	50	\N	/data/product_images/123_Woodford_Reserve_750ml.jpg	2026-01-07 18:24:49.609209	23.01	35.00	0.10	0.00	f	Premium Kentucky bourbon. Complex spice and fruit notes.
124	Woodford Reserve 1L	Whiskey	38.06	50	\N	/data/product_images/124_Woodford_Reserve_1L.jpg	2026-01-07 18:24:49.609209	28.19	35.00	0.10	0.00	f	Premium Kentucky bourbon. Complex spice and fruit notes.
125	Woodford Reserve 1.75L	Whiskey	62.07	50	\N	/data/product_images/125_Woodford_Reserve_1.75L.jpg	2026-01-07 18:24:49.609209	45.98	35.00	0.25	0.00	f	Premium Kentucky bourbon. Complex spice and fruit notes.
126	Four Roses 50ml	Whiskey	3.22	50	\N	/data/product_images/126_Four_Roses_50ml.jpg	2026-01-07 18:24:49.609209	2.39	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
127	Four Roses 375ml	Whiskey	17.16	50	\N	/data/product_images/127_Four_Roses_375ml.jpg	2026-01-07 18:24:49.609209	12.71	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
128	Four Roses 750ml	Whiskey	32.81	50	\N	/data/product_images/128_Four_Roses_750ml.jpg	2026-01-07 18:24:49.609209	24.30	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
341	Robert Mondavi Cabernet 375ml	Wine - Red	10.02	50	\N	/data/product_images/341_Robert_Mondavi_Cabernet_375ml.jpg	2026-01-07 18:24:49.629102	7.42	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
342	Robert Mondavi Cabernet 750ml	Wine - Red	17.62	50	\N	/data/product_images/342_Robert_Mondavi_Cabernet_750ml.jpg	2026-01-07 18:24:49.629102	13.05	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
343	Robert Mondavi Cabernet 1.75L	Wine - Red	36.96	50	\N	/data/product_images/343_Robert_Mondavi_Cabernet_1.75L.jpg	2026-01-07 18:24:49.629102	27.38	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
344	Yellow Tail Cabernet 375ml	Wine - Red	9.70	50	\N	/data/product_images/344_Yellow_Tail_Cabernet_375ml.jpg	2026-01-07 18:24:49.629102	7.19	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
345	Yellow Tail Cabernet 750ml	Wine - Red	17.52	50	\N	/data/product_images/345_Yellow_Tail_Cabernet_750ml.jpg	2026-01-07 18:24:49.629102	12.98	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
346	Yellow Tail Cabernet 1.75L	Wine - Red	37.14	50	\N	/data/product_images/346_Yellow_Tail_Cabernet_1.75L.jpg	2026-01-07 18:24:49.629102	27.51	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
347	Barefoot Cabernet 375ml	Wine - Red	10.12	50	\N	/data/product_images/347_Barefoot_Cabernet_375ml.jpg	2026-01-07 18:24:49.629102	7.50	35.00	0.10	0.00	f	Full-bodied Cabernet. Rich plum and dark cherry, silky tannins.
348	Barefoot Cabernet 750ml	Wine - Red	17.89	50	\N	/data/product_images/348_Barefoot_Cabernet_750ml.jpg	2026-01-07 18:24:49.629102	13.25	35.00	0.10	0.00	f	Full-bodied Cabernet. Rich plum and dark cherry, silky tannins.
349	Barefoot Cabernet 1.75L	Wine - Red	34.63	50	\N	/data/product_images/349_Barefoot_Cabernet_1.75L.jpg	2026-01-07 18:24:49.629102	25.65	35.00	0.25	0.00	f	Full-bodied Cabernet. Rich plum and dark cherry, silky tannins.
351	Gallo Cabernet 750ml	Wine - Red	17.23	50	\N	/data/product_images/351_Gallo_Cabernet_750ml.jpg	2026-01-07 18:24:49.629102	12.76	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
352	Gallo Cabernet 1.75L	Wine - Red	35.02	50	\N	/data/product_images/352_Gallo_Cabernet_1.75L.jpg	2026-01-07 18:24:49.629102	25.94	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
353	Woodbridge 375ml	Wine - Red	10.24	50	\N	/data/product_images/353_Woodbridge_375ml.jpg	2026-01-07 18:24:49.629102	7.59	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
354	Woodbridge 750ml	Wine - Red	18.25	50	\N	/data/product_images/354_Woodbridge_750ml.jpg	2026-01-07 18:24:49.629102	13.52	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
355	Woodbridge 1.75L	Wine - Red	37.05	50	\N	/data/product_images/355_Woodbridge_1.75L.jpg	2026-01-07 18:24:49.629102	27.44	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
356	Santa Margherita Barbera 375ml	Wine - Red	10.06	50	\N	/data/product_images/356_Santa_Margherita_Barbera_375ml.jpg	2026-01-07 18:24:49.629102	7.45	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
357	Santa Margherita Barbera 750ml	Wine - Red	17.16	50	\N	/data/product_images/357_Santa_Margherita_Barbera_750ml.jpg	2026-01-07 18:24:49.629102	12.71	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
358	Santa Margherita Barbera 1.75L	Wine - Red	37.42	50	\N	/data/product_images/358_Santa_Margherita_Barbera_1.75L.jpg	2026-01-07 18:24:49.629102	27.72	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
359	Yellowstone Merlot 375ml	Wine - Red	10.25	50	\N	/data/product_images/359_Yellowstone_Merlot_375ml.jpg	2026-01-07 18:24:49.629102	7.59	35.00	0.10	0.00	f	Smooth red wine with plum and cherry notes
360	Yellowstone Merlot 750ml	Wine - Red	18.48	50	\N	/data/product_images/360_Yellowstone_Merlot_750ml.jpg	2026-01-07 18:24:49.629102	13.69	35.00	0.10	0.00	f	Smooth red wine with plum and cherry notes
361	Yellowstone Merlot 1.75L	Wine - Red	35.64	50	\N	/data/product_images/361_Yellowstone_Merlot_1.75L.jpg	2026-01-07 18:24:49.629102	26.40	35.00	0.25	0.00	f	Smooth red wine with plum and cherry notes
362	Black Box Red 375ml	Wine - Red	9.59	50	\N	/data/product_images/362_Black_Box_Red_375ml.jpg	2026-01-07 18:24:49.629102	7.10	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
1072	Fireball Cinnamon Whisky 750ml	Spirits	29.99	\N	\N	\N	2026-01-08 16:19:01.852975	20.99	35.00	0.00	0.00	f	Cinnamon whiskey liqueur
1073	Fireball Cinnamon Whisky 1.75L	Spirits	59.99	\N	\N	\N	2026-01-08 16:19:01.855789	41.99	35.00	0.00	0.00	f	Cinnamon whiskey liqueur
1074	Sips Champagne 187ml (mini)	Champagne	8.99	\N	\N	\N	2026-01-08 16:19:01.856254	6.29	35.00	0.00	0.00	f	Premium sparkling champagne
1075	Sips Champagne 750ml	Champagne	19.99	\N	\N	\N	2026-01-08 16:19:01.856755	13.99	35.00	0.00	0.00	f	Premium sparkling champagne
1076	Sips Champagne 1.5L	Champagne	34.99	\N	\N	\N	2026-01-08 16:19:01.85719	24.49	35.00	0.00	0.00	f	Premium sparkling champagne
1056	Chablis 1L	Wine - White	22.13	0	\N	\N	2026-01-08 14:43:00.529192	15.49	35.00	0.10	0.00	f	Chablis white wine - 1L
135	Knob Creek 1.75L	Whiskey	63.74	50	\N	/data/product_images/135_Knob_Creek_1.75L.jpg	2026-01-07 18:24:49.609209	47.21	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
136	Elijah Craig 50ml	Whiskey	3.34	50	\N	/data/product_images/136_Elijah_Craig_50ml.jpg	2026-01-07 18:24:49.609209	2.47	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
137	Elijah Craig 375ml	Whiskey	17.50	50	\N	/data/product_images/137_Elijah_Craig_375ml.jpg	2026-01-07 18:24:49.609209	12.96	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
363	Black Box Red 750ml	Wine - Red	18.76	50	\N	/data/product_images/363_Black_Box_Red_750ml.jpg	2026-01-07 18:24:49.629102	13.90	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
364	Black Box Red 1.75L	Wine - Red	35.36	50	\N	/data/product_images/364_Black_Box_Red_1.75L.jpg	2026-01-07 18:24:49.629102	26.19	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
368	Barefoot Pinot Noir 375ml	Wine - Red	10.20	50	\N	/data/product_images/368_Barefoot_Pinot_Noir_375ml.jpg	2026-01-07 18:24:49.629102	7.56	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
369	Barefoot Pinot Noir 750ml	Wine - Red	18.70	50	\N	/data/product_images/369_Barefoot_Pinot_Noir_750ml.jpg	2026-01-07 18:24:49.629102	13.85	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
370	Barefoot Pinot Noir 1.75L	Wine - Red	36.29	50	\N	/data/product_images/370_Barefoot_Pinot_Noir_1.75L.jpg	2026-01-07 18:24:49.629102	26.88	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
371	La Crema Pinot Noir 375ml	Wine - Red	9.84	50	\N	/data/product_images/371_La_Crema_Pinot_Noir_375ml.jpg	2026-01-07 18:24:49.629102	7.29	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
372	La Crema Pinot Noir 750ml	Wine - Red	18.58	50	\N	/data/product_images/372_La_Crema_Pinot_Noir_750ml.jpg	2026-01-07 18:24:49.629102	13.76	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
373	La Crema Pinot Noir 1.75L	Wine - Red	34.61	50	\N	/data/product_images/373_La_Crema_Pinot_Noir_1.75L.jpg	2026-01-07 18:24:49.629102	25.64	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
374	A to Z Pinot Noir 375ml	Wine - Red	9.97	50	\N	/data/product_images/374_A_to_Z_Pinot_Noir_375ml.jpg	2026-01-07 18:24:49.629102	7.39	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
375	A to Z Pinot Noir 750ml	Wine - Red	17.40	50	\N	/data/product_images/375_A_to_Z_Pinot_Noir_750ml.jpg	2026-01-07 18:24:49.629102	12.89	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
376	A to Z Pinot Noir 1.75L	Wine - Red	35.56	50	\N	/data/product_images/376_A_to_Z_Pinot_Noir_1.75L.jpg	2026-01-07 18:24:49.629102	26.34	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
378	Columbia Crest Merlot 750ml	Wine - Red	18.78	50	\N	/data/product_images/378_Columbia_Crest_Merlot_750ml.jpg	2026-01-07 18:24:49.629102	13.91	35.00	0.10	0.00	f	Smooth red wine with plum and cherry notes
379	Columbia Crest Merlot 1.75L	Wine - Red	35.01	50	\N	/data/product_images/379_Columbia_Crest_Merlot_1.75L.jpg	2026-01-07 18:24:49.629102	25.93	35.00	0.25	0.00	f	Smooth red wine with plum and cherry notes
380	Vella Italian Red 375ml	Wine - Red	10.26	50	\N	/data/product_images/380_Vella_Italian_Red_375ml.jpg	2026-01-07 18:24:49.629102	7.60	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
381	Vella Italian Red 750ml	Wine - Red	18.15	50	\N	/data/product_images/381_Vella_Italian_Red_750ml.jpg	2026-01-07 18:24:49.629102	13.44	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
382	Vella Italian Red 1.75L	Wine - Red	35.21	50	\N	/data/product_images/382_Vella_Italian_Red_1.75L.jpg	2026-01-07 18:24:49.629102	26.08	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
383	Sutter Home 375ml	Wine - Red	9.71	50	\N	/data/product_images/383_Sutter_Home_375ml.jpg	2026-01-07 18:24:49.629102	7.19	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
384	Sutter Home 750ml	Wine - Red	18.44	50	\N	/data/product_images/384_Sutter_Home_750ml.jpg	2026-01-07 18:24:49.629102	13.66	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
385	Sutter Home 1.75L	Wine - Red	37.59	50	\N	/data/product_images/385_Sutter_Home_1.75L.jpg	2026-01-07 18:24:49.629102	27.84	35.00	0.25	0.00	f	Red wine. Full-bodied with fruit-forward character.
386	Kendall Jackson Chardonnay 375ml	Wine - White	9.16	50	\N	/data/product_images/386_Kendall_Jackson_Chardonnay_375.jpg	2026-01-07 18:24:49.631936	6.79	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
387	Kendall Jackson Chardonnay 750ml	Wine - White	16.36	50	\N	/data/product_images/387_Kendall_Jackson_Chardonnay_750.jpg	2026-01-07 18:24:49.631936	12.12	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
388	Kendall Jackson Chardonnay 1.75L	Wine - White	32.98	50	\N	/data/product_images/388_Kendall_Jackson_Chardonnay_1.7.jpg	2026-01-07 18:24:49.631936	24.43	35.00	0.25	0.00	f	Rich white wine with butter and oak flavors
389	Barefoot Chardonnay 375ml	Wine - White	8.50	50	\N	/data/product_images/389_Barefoot_Chardonnay_375ml.jpg	2026-01-07 18:24:49.631936	6.30	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
390	Barefoot Chardonnay 750ml	Wine - White	15.43	50	\N	/data/product_images/390_Barefoot_Chardonnay_750ml.jpg	2026-01-07 18:24:49.631936	11.43	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
391	Barefoot Chardonnay 1.75L	Wine - White	31.49	50	\N	/data/product_images/391_Barefoot_Chardonnay_1.75L.jpg	2026-01-07 18:24:49.631936	23.33	35.00	0.25	0.00	f	Rich white wine with butter and oak flavors
392	Yellowstone Chardonnay 375ml	Wine - White	8.51	50	\N	/data/product_images/392_Yellowstone_Chardonnay_375ml.jpg	2026-01-07 18:24:49.631936	6.30	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
393	Yellowstone Chardonnay 750ml	Wine - White	16.02	50	\N	/data/product_images/393_Yellowstone_Chardonnay_750ml.jpg	2026-01-07 18:24:49.631936	11.87	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
394	Yellowstone Chardonnay 1.75L	Wine - White	31.63	50	\N	/data/product_images/394_Yellowstone_Chardonnay_1.75L.jpg	2026-01-07 18:24:49.631936	23.43	35.00	0.25	0.00	f	Rich white wine with butter and oak flavors
1077	Gin Smash Cooler 355ml	Ready-To-Drink	6.99	\N	\N	\N	2026-01-08 16:19:55.163158	4.89	35.00	0.00	0.00	f	Gin smash flavored cooler
1078	Gin Smash Cooler 473ml	Ready-To-Drink	8.99	\N	\N	\N	2026-01-08 16:19:55.170086	6.29	35.00	0.00	0.00	f	Gin smash flavored cooler
1079	Cottage Springs Water 500ml	Water	2.99	\N	\N	\N	2026-01-08 16:19:55.17069	2.09	35.00	0.00	0.00	f	Spring water
1080	Cottage Springs Water 1L	Water	3.99	\N	\N	\N	2026-01-08 16:19:55.172018	2.79	35.00	0.00	0.00	f	Spring water
1081	No Way Ice Tea 355ml	Iced Tea	3.49	\N	\N	\N	2026-01-08 16:19:55.173765	2.44	35.00	0.00	0.00	f	Non-alcoholic ice tea
106	Maker's Mark 50ml	Whiskey	3.21	50	\N	/data/product_images/106_Maker's_Mark_50ml.jpg	2026-01-07 18:24:49.609209	2.38	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
107	Maker's Mark 375ml	Whiskey	18.01	50	\N	/data/product_images/107_Maker's_Mark_375ml.jpg	2026-01-07 18:24:49.609209	13.34	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
395	Santa Margherita 375ml	Wine - White	8.37	50	\N	/data/product_images/395_Santa_Margherita_375ml.jpg	2026-01-07 18:24:49.631936	6.20	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
396	Santa Margherita 750ml	Wine - White	15.24	50	\N	/data/product_images/396_Santa_Margherita_750ml.jpg	2026-01-07 18:24:49.631936	11.29	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
397	Santa Margherita 1.75L	Wine - White	32.72	50	\N	/data/product_images/397_Santa_Margherita_1.75L.jpg	2026-01-07 18:24:49.631936	24.24	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
398	Chablis 375ml	Wine - White	9.14	50	\N	/data/product_images/398_Chablis_375ml.jpg	2026-01-07 18:24:49.631936	6.77	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
399	Chablis 750ml	Wine - White	16.64	50	\N	/data/product_images/399_Chablis_750ml.jpg	2026-01-07 18:24:49.631936	12.33	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
401	Barefoot Sauvignon Blanc 375ml	Wine - White	8.96	50	\N	/data/product_images/401_Barefoot_Sauvignon_Blanc_375ml.jpg	2026-01-07 18:24:49.631936	6.64	35.00	0.10	0.00	f	Crisp white wine with herbaceous and tropical notes
402	Barefoot Sauvignon Blanc 750ml	Wine - White	16.70	50	\N	/data/product_images/402_Barefoot_Sauvignon_Blanc_750ml.jpg	2026-01-07 18:24:49.631936	12.37	35.00	0.10	0.00	f	Crisp white wine with herbaceous and tropical notes
403	Barefoot Sauvignon Blanc 1.75L	Wine - White	32.90	50	\N	/data/product_images/403_Barefoot_Sauvignon_Blanc_1.75L.jpg	2026-01-07 18:24:49.631936	24.37	35.00	0.25	0.00	f	Crisp white wine with herbaceous and tropical notes
409	Sancerre 1.75L	Wine - White	33.16	50	\N	/data/product_images/409_Sancerre_1.75L.jpg	2026-01-07 18:24:49.631936	24.56	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
410	Villa Maria Sauvignon 375ml	Wine - White	8.43	50	\N	/data/product_images/410_Villa_Maria_Sauvignon_375ml.jpg	2026-01-07 18:24:49.631936	6.24	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
411	Villa Maria Sauvignon 750ml	Wine - White	15.78	50	\N	/data/product_images/411_Villa_Maria_Sauvignon_750ml.jpg	2026-01-07 18:24:49.631936	11.69	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
412	Villa Maria Sauvignon 1.75L	Wine - White	32.24	50	\N	/data/product_images/412_Villa_Maria_Sauvignon_1.75L.jpg	2026-01-07 18:24:49.631936	23.88	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
413	Fiddlehead 375ml	Wine - White	9.03	50	\N	/data/product_images/413_Fiddlehead_375ml.jpg	2026-01-07 18:24:49.631936	6.69	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
414	Fiddlehead 750ml	Wine - White	15.33	50	\N	/data/product_images/414_Fiddlehead_750ml.jpg	2026-01-07 18:24:49.631936	11.36	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
415	Fiddlehead 1.75L	Wine - White	32.70	50	\N	/data/product_images/415_Fiddlehead_1.75L.jpg	2026-01-07 18:24:49.631936	24.22	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
416	Barefoot Pinot Grigio 375ml	Wine - White	9.16	50	\N	/data/product_images/416_Barefoot_Pinot_Grigio_375ml.jpg	2026-01-07 18:24:49.631936	6.79	35.00	0.10	0.00	f	Light white wine with green apple and citrus notes
417	Barefoot Pinot Grigio 750ml	Wine - White	16.57	50	\N	/data/product_images/417_Barefoot_Pinot_Grigio_750ml.jpg	2026-01-07 18:24:49.631936	12.27	35.00	0.10	0.00	f	Light white wine with green apple and citrus notes
418	Barefoot Pinot Grigio 1.75L	Wine - White	31.11	50	\N	/data/product_images/418_Barefoot_Pinot_Grigio_1.75L.jpg	2026-01-07 18:24:49.631936	23.04	35.00	0.25	0.00	f	Light white wine with green apple and citrus notes
419	Barefoot Riesling 375ml	Wine - White	9.13	50	\N	/data/product_images/419_Barefoot_Riesling_375ml.jpg	2026-01-07 18:24:49.631936	6.76	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
420	Barefoot Riesling 750ml	Wine - White	16.70	50	\N	/data/product_images/420_Barefoot_Riesling_750ml.jpg	2026-01-07 18:24:49.631936	12.37	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
421	Barefoot Riesling 1.75L	Wine - White	33.05	50	\N	/data/product_images/421_Barefoot_Riesling_1.75L.jpg	2026-01-07 18:24:49.631936	24.48	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
422	Yellow Tail Riesling 375ml	Wine - White	8.43	50	\N	/data/product_images/422_Yellow_Tail_Riesling_375ml.jpg	2026-01-07 18:24:49.631936	6.24	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
423	Yellow Tail Riesling 750ml	Wine - White	15.69	50	\N	/data/product_images/423_Yellow_Tail_Riesling_750ml.jpg	2026-01-07 18:24:49.631936	11.62	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
424	Yellow Tail Riesling 1.75L	Wine - White	32.62	50	\N	/data/product_images/424_Yellow_Tail_Riesling_1.75L.jpg	2026-01-07 18:24:49.631936	24.16	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
425	Barefoot Bubbly Brut 375ml	Wine - White	8.87	50	\N	/data/product_images/425_Barefoot_Bubbly_Brut_375ml.jpg	2026-01-07 18:24:49.631936	6.57	35.00	0.10	0.00	f	California sparkling wine. Bright bubbles, fruity, celebratory.
426	Barefoot Bubbly Brut 750ml	Wine - White	15.30	50	\N	/data/product_images/426_Barefoot_Bubbly_Brut_750ml.jpg	2026-01-07 18:24:49.631936	11.33	35.00	0.10	0.00	f	California sparkling wine. Bright bubbles, fruity, celebratory.
427	Barefoot Bubbly Brut 1.75L	Wine - White	32.83	50	\N	/data/product_images/427_Barefoot_Bubbly_Brut_1.75L.jpg	2026-01-07 18:24:49.631936	24.32	35.00	0.25	0.00	f	California sparkling wine. Bright bubbles, fruity, celebratory.
428	Barefoot Moscato 375ml	Wine - White	8.67	50	\N	/data/product_images/428_Barefoot_Moscato_375ml.jpg	2026-01-07 18:24:49.631936	6.42	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
429	Barefoot Moscato 750ml	Wine - White	16.33	50	\N	/data/product_images/429_Barefoot_Moscato_750ml.jpg	2026-01-07 18:24:49.631936	12.10	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
435	Moët & Chandon 750ml	Champagne	76.39	50	\N	/data/product_images/435_Moët_&_Chandon_750ml.jpg	2026-01-07 18:24:49.634988	56.59	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
1082	No Way Ice Tea 473ml	Iced Tea	4.49	\N	\N	\N	2026-01-08 16:19:55.174225	3.14	35.00	0.00	0.00	f	Non-alcoholic ice tea
1083	Keystone Light Beer 355ml (single)	Beer	2.49	\N	\N	\N	2026-01-08 16:19:55.174641	1.74	35.00	0.00	0.00	f	Light lager
1084	Keystone Light Beer 473ml (single)	Beer	3.29	\N	\N	\N	2026-01-08 16:19:55.175014	2.30	35.00	0.00	0.00	f	Light lager
1085	Keystone Light 24-pack	Beer	29.99	\N	\N	\N	2026-01-08 16:19:55.175332	20.99	35.00	0.00	0.00	f	Light lager 24-pack
1086	5 of Diamonds Energy Drink 355ml	Energy Drink	2.99	\N	\N	\N	2026-01-08 16:22:21.777673	2.09	35.00	0.00	0.00	f	Premium energy drink
1087	5 of Diamonds Energy Drink 473ml	Energy Drink	3.99	\N	\N	\N	2026-01-08 16:22:21.783071	2.79	35.00	0.00	0.00	f	Premium energy drink
1180	run	Beer	5.49	\N	\N	\N	2026-01-27 21:28:59.979813	3.84	35.00	0.00	0.00	f	\N
49	San Pellegrino San Pellegrino	Water	4.50	50	\N	/data/product_images/49_San_Pellegrino_San_Pellegrino.jpg	2026-01-07 18:15:08.023848	3.33	35.00	0.10	0.00	f	Italian sparkling water. Crisp, elegant.
129	Four Roses 1L	Whiskey	39.28	50	\N	/data/product_images/129_Four_Roses_1L.jpg	2026-01-07 18:24:49.609209	29.10	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
130	Four Roses 1.75L	Whiskey	65.53	50	\N	/data/product_images/130_Four_Roses_1.75L.jpg	2026-01-07 18:24:49.609209	48.54	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
131	Knob Creek 50ml	Whiskey	3.31	50	\N	/data/product_images/131_Knob_Creek_50ml.jpg	2026-01-07 18:24:49.609209	2.45	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
138	Elijah Craig 750ml	Whiskey	30.66	50	\N	/data/product_images/138_Elijah_Craig_750ml.jpg	2026-01-07 18:24:49.609209	22.71	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
436	Moët & Chandon 1.75L	Champagne	160.96	50	\N	/data/product_images/436_Moët_&_Chandon_1.75L.jpg	2026-01-07 18:24:49.634988	119.23	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
437	Veuve Clicquot 375ml	Champagne	44.70	50	\N	/data/product_images/437_Veuve_Clicquot_375ml.jpg	2026-01-07 18:24:49.634988	33.11	35.00	0.10	0.00	f	Classic Champagne. Rich, balanced, celebratory.
438	Veuve Clicquot 750ml	Champagne	78.28	50	\N	/data/product_images/438_Veuve_Clicquot_750ml.jpg	2026-01-07 18:24:49.634988	57.99	35.00	0.10	0.00	f	Classic Champagne. Rich, balanced, celebratory.
439	Veuve Clicquot 1.75L	Champagne	153.10	50	\N	/data/product_images/439_Veuve_Clicquot_1.75L.jpg	2026-01-07 18:24:49.634988	113.41	35.00	0.25	0.00	f	Classic Champagne. Rich, balanced, celebratory.
440	Louis Roederer Cristal 375ml	Champagne	43.01	50	\N	/data/product_images/440_Louis_Roederer_Cristal_375ml.jpg	2026-01-07 18:24:49.634988	31.86	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
441	Louis Roederer Cristal 750ml	Champagne	81.13	50	\N	/data/product_images/441_Louis_Roederer_Cristal_750ml.jpg	2026-01-07 18:24:49.634988	60.10	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
442	Louis Roederer Cristal 1.75L	Champagne	155.42	50	\N	/data/product_images/442_Louis_Roederer_Cristal_1.75L.jpg	2026-01-07 18:24:49.634988	115.13	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
443	Bollinger 375ml	Champagne	43.71	50	\N	/data/product_images/443_Bollinger_375ml.jpg	2026-01-07 18:24:49.634988	32.38	35.00	0.10	0.00	f	Prestigious Champagne. Complex, aged, elegant.
444	Bollinger 750ml	Champagne	76.63	50	\N	/data/product_images/444_Bollinger_750ml.jpg	2026-01-07 18:24:49.634988	56.76	35.00	0.10	0.00	f	Prestigious Champagne. Complex, aged, elegant.
445	Bollinger 1.75L	Champagne	166.29	50	\N	/data/product_images/445_Bollinger_1.75L.jpg	2026-01-07 18:24:49.634988	123.18	35.00	0.25	0.00	f	Prestigious Champagne. Complex, aged, elegant.
446	Taittinger 375ml	Champagne	43.37	50	\N	/data/product_images/446_Taittinger_375ml.jpg	2026-01-07 18:24:49.634988	32.13	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
447	Taittinger 750ml	Champagne	80.22	50	\N	/data/product_images/447_Taittinger_750ml.jpg	2026-01-07 18:24:49.634988	59.42	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
448	Taittinger 1.75L	Champagne	159.37	50	\N	/data/product_images/448_Taittinger_1.75L.jpg	2026-01-07 18:24:49.634988	118.05	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
449	Krug 375ml	Champagne	42.38	50	\N	/data/product_images/449_Krug_375ml.jpg	2026-01-07 18:24:49.634988	31.39	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
450	Krug 750ml	Champagne	83.72	50	\N	/data/product_images/450_Krug_750ml.jpg	2026-01-07 18:24:49.634988	62.01	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
451	Krug 1.75L	Champagne	167.68	50	\N	/data/product_images/451_Krug_1.75L.jpg	2026-01-07 18:24:49.634988	124.21	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
452	Perrier-Jouët 375ml	Champagne	43.42	50	\N	/data/product_images/452_Perrier-Jouët_375ml.jpg	2026-01-07 18:24:49.634988	32.16	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
453	Perrier-Jouët 750ml	Champagne	79.20	50	\N	/data/product_images/453_Perrier-Jouët_750ml.jpg	2026-01-07 18:24:49.634988	58.67	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
454	Perrier-Jouët 1.75L	Champagne	157.71	50	\N	/data/product_images/454_Perrier-Jouët_1.75L.jpg	2026-01-07 18:24:49.634988	116.82	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
455	Laurent Perrier 375ml	Champagne	43.09	50	\N	/data/product_images/455_Laurent_Perrier_375ml.jpg	2026-01-07 18:24:49.634988	31.92	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
456	Laurent Perrier 750ml	Champagne	77.56	50	\N	/data/product_images/456_Laurent_Perrier_750ml.jpg	2026-01-07 18:24:49.634988	57.45	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
457	Laurent Perrier 1.75L	Champagne	163.04	50	\N	/data/product_images/457_Laurent_Perrier_1.75L.jpg	2026-01-07 18:24:49.634988	120.77	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
458	Barefoot Bubbly 375ml	Champagne	45.04	50	\N	/data/product_images/458_Barefoot_Bubbly_375ml.jpg	2026-01-07 18:24:49.634988	33.36	35.00	0.10	0.00	f	California sparkling wine. Bright bubbles, fruity, celebratory.
459	Barefoot Bubbly 750ml	Champagne	80.99	50	\N	/data/product_images/459_Barefoot_Bubbly_750ml.jpg	2026-01-07 18:24:49.634988	59.99	35.00	0.10	0.00	f	California sparkling wine. Bright bubbles, fruity, celebratory.
50	Various Premium Red Wine	Wine	45.00	50	\N	/data/product_images/50_Various_Premium_Red_Wine.jpg	2026-01-07 18:15:08.023848	33.33	35.00	0.10	0.00	f	\N
51	Various Premium White Wine	Wine	45.00	50	\N	/data/product_images/51_Various_Premium_White_Wine.jpg	2026-01-07 18:15:08.023848	33.33	35.00	0.10	0.00	f	\N
1088	Pabst Blue Ribbon 355ml (single)	Beer	2.39	\N	\N	\N	2026-01-08 16:23:40.837316	1.67	35.00	0.00	0.00	f	Classic American lager
1089	Pabst Blue Ribbon 473ml (single)	Beer	3.19	\N	\N	\N	2026-01-08 16:23:40.84044	2.23	35.00	0.00	0.00	f	Classic American lager
1090	Pabst Blue Ribbon 24-pack	Beer	28.99	\N	\N	\N	2026-01-08 16:23:40.841469	20.29	35.00	0.00	0.00	f	Classic American lager 24-pack
132	Knob Creek 375ml	Whiskey	18.04	50	\N	/data/product_images/132_Knob_Creek_375ml.jpg	2026-01-07 18:24:49.609209	13.36	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
133	Knob Creek 750ml	Whiskey	32.43	50	\N	/data/product_images/133_Knob_Creek_750ml.jpg	2026-01-07 18:24:49.609209	24.02	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
134	Knob Creek 1L	Whiskey	38.83	50	\N	/data/product_images/134_Knob_Creek_1L.jpg	2026-01-07 18:24:49.609209	28.76	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
139	Elijah Craig 1L	Whiskey	39.54	50	\N	/data/product_images/139_Elijah_Craig_1L.jpg	2026-01-07 18:24:49.609209	29.29	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
140	Elijah Craig 1.75L	Whiskey	67.14	50	\N	/data/product_images/140_Elijah_Craig_1.75L.jpg	2026-01-07 18:24:49.609209	49.73	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
141	Angel's Envy 50ml	Whiskey	3.06	50	\N	/data/product_images/141_Angel's_Envy_50ml.jpg	2026-01-07 18:24:49.609209	2.27	35.00	0.10	0.00	f	Bourbon finished in port barrels. Rich, smooth, creamy vanilla notes.
142	Angel's Envy 375ml	Whiskey	17.51	50	\N	/data/product_images/142_Angel's_Envy_375ml.jpg	2026-01-07 18:24:49.609209	12.97	35.00	0.10	0.00	f	Bourbon finished in port barrels. Rich, smooth, creamy vanilla notes.
143	Angel's Envy 750ml	Whiskey	32.27	50	\N	/data/product_images/143_Angel's_Envy_750ml.jpg	2026-01-07 18:24:49.609209	23.90	35.00	0.10	0.00	f	Bourbon finished in port barrels. Rich, smooth, creamy vanilla notes.
144	Angel's Envy 1L	Whiskey	40.13	50	\N	/data/product_images/144_Angel's_Envy_1L.jpg	2026-01-07 18:24:49.609209	29.73	35.00	0.10	0.00	f	Bourbon finished in port barrels. Rich, smooth, creamy vanilla notes.
145	Angel's Envy 1.75L	Whiskey	66.20	50	\N	/data/product_images/145_Angel's_Envy_1.75L.jpg	2026-01-07 18:24:49.609209	49.04	35.00	0.25	0.00	f	Bourbon finished in port barrels. Rich, smooth, creamy vanilla notes.
23	Red Wine (House) 750ml	Wine	15.99	100	\N	/data/product_images/23_Red_Wine_(House)_750ml.jpg	2026-01-07 18:10:03.962356	11.84	35.00	0.10	0.00	f	\N
24	White Wine (House) 750ml	Wine	14.99	100	\N	/data/product_images/24_White_Wine_(House)_750ml.jpg	2026-01-07 18:10:03.962356	11.10	35.00	0.10	0.00	f	\N
35	Premium Hot Chocolate	Coffee	5.00	50	\N	/data/product_images/35_Premium_Hot_Chocolate.jpg	2026-01-07 18:15:08.023848	3.70	35.00	0.10	0.00	f	\N
36	Various Premium Coffee	Coffee	6.00	50	\N	/data/product_images/36_Various_Premium_Coffee.jpg	2026-01-07 18:15:08.023848	4.44	35.00	0.10	0.00	f	\N
37	Monster Monster Energy	Energy	4.50	50	\N	/data/product_images/37_Monster_Monster_Energy.jpg	2026-01-07 18:15:08.023848	3.33	35.00	0.10	0.00	f	\N
39	Premium Cranberry Juice	Juice	6.00	50	\N	/data/product_images/39_Premium_Cranberry_Juice.jpg	2026-01-07 18:15:08.023848	4.44	35.00	0.10	0.00	f	\N
40	Fresh Fresh Orange Juice	Juice	8.00	50	\N	/data/product_images/40_Fresh_Fresh_Orange_Juice.jpg	2026-01-07 18:15:08.023848	5.93	35.00	0.10	0.00	f	\N
41	Premium Assorted Nuts	Snacks	8.00	50	\N	/data/product_images/41_Premium_Assorted_Nuts.jpg	2026-01-07 18:15:08.023848	5.93	35.00	0.10	0.00	f	\N
42	Coca-Cola Coca-Cola	Soft Drinks	3.50	50	\N	/data/product_images/42_Coca-Cola_Coca-Cola.jpg	2026-01-07 18:15:08.023848	2.59	35.00	0.10	0.00	f	\N
43	Coca-Cola Sprite	Soft Drinks	3.50	50	\N	/data/product_images/43_Coca-Cola_Sprite.jpg	2026-01-07 18:15:08.023848	2.59	35.00	0.10	0.00	f	\N
44	Grey Goose Grey Goose Vodka	Spirits	60.00	50	\N	/data/product_images/44_Grey_Goose_Grey_Goose_Vodka.jpg	2026-01-07 18:15:08.023848	44.44	35.00	0.10	0.00	f	Neutral spirit, versatile for mixed drinks
47	Fiji Fiji Water	Water	4.00	50	\N	/data/product_images/47_Fiji_Fiji_Water.jpg	2026-01-07 18:15:08.023848	2.96	35.00	0.10	0.00	f	\N
1091	Too Hoots Hard Ice Tea 355ml	Hard Seltzers	4.49	\N	\N	\N	2026-01-08 16:25:39.586941	3.14	35.00	0.00	0.00	f	Hard ice tea beverage
1092	Too Hoots Hard Ice Tea 473ml	Hard Seltzers	5.49	\N	\N	\N	2026-01-08 16:25:39.589312	3.84	35.00	0.00	0.00	f	Hard ice tea beverage
1093	Absolute Coolers 355ml	Ready-To-Drink	5.99	\N	\N	\N	2026-01-08 16:25:39.589848	4.19	35.00	0.00	0.00	f	Vodka-based cooler
146	Proper Twelve 50ml	Whiskey	3.15	50	\N	/data/product_images/146_Proper_Twelve_50ml.jpg	2026-01-07 18:24:49.609209	2.33	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
147	Proper Twelve 375ml	Whiskey	18.21	50	\N	/data/product_images/147_Proper_Twelve_375ml.jpg	2026-01-07 18:24:49.609209	13.49	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
148	Proper Twelve 750ml	Whiskey	31.50	50	\N	/data/product_images/148_Proper_Twelve_750ml.jpg	2026-01-07 18:24:49.609209	23.33	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
1094	Absolute Coolers 473ml	Ready-To-Drink	7.49	\N	\N	\N	2026-01-08 16:25:39.590426	5.24	35.00	0.00	0.00	f	Vodka-based cooler
1095	American Vintage Whiskey 750ml	Spirits	34.99	\N	\N	\N	2026-01-08 16:25:39.590904	24.49	35.00	0.00	0.00	f	Premium American whiskey
1096	Arizona Hard Ice Tea 355ml	Hard Seltzers	4.29	\N	\N	\N	2026-01-08 16:25:39.591387	3.00	35.00	0.00	0.00	f	Hard ice tea beverage
1097	Arizona Hard Ice Tea 473ml	Hard Seltzers	5.29	\N	\N	\N	2026-01-08 16:25:39.591879	3.70	35.00	0.00	0.00	f	Hard ice tea beverage
1098	Bacardi Coolers 355ml	Ready-To-Drink	5.99	\N	\N	\N	2026-01-08 16:25:39.59239	4.19	35.00	0.00	0.00	f	Rum-based cooler
1099	Bacardi Coolers 473ml	Ready-To-Drink	7.49	\N	\N	\N	2026-01-08 16:25:39.592926	5.24	35.00	0.00	0.00	f	Rum-based cooler
1100	Mudslide Cocktail 355ml	Ready-To-Drink	6.99	\N	\N	\N	2026-01-08 16:25:39.59338	4.89	35.00	0.00	0.00	f	Ready-to-drink mudslide
149	Proper Twelve 1L	Whiskey	38.98	50	\N	/data/product_images/149_Proper_Twelve_1L.jpg	2026-01-07 18:24:49.609209	28.87	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
1101	Blackfly Cocktail 355ml	Ready-To-Drink	6.99	\N	\N	\N	2026-01-08 16:25:39.593906	4.89	35.00	0.00	0.00	f	Ready-to-drink cocktail
150	Proper Twelve 1.75L	Whiskey	65.43	50	\N	/data/product_images/150_Proper_Twelve_1.75L.jpg	2026-01-07 18:24:49.609209	48.47	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
151	Smirnoff 50ml	Vodka	3.06	50	\N	/data/product_images/151_Smirnoff_50ml.jpg	2026-01-07 18:24:49.614561	2.27	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
152	Smirnoff 375ml	Vodka	16.97	50	\N	/data/product_images/152_Smirnoff_375ml.jpg	2026-01-07 18:24:49.614561	12.57	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
153	Smirnoff 750ml	Vodka	28.61	50	\N	/data/product_images/153_Smirnoff_750ml.jpg	2026-01-07 18:24:49.614561	21.19	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
154	Smirnoff 1L	Vodka	35.63	50	\N	/data/product_images/154_Smirnoff_1L.jpg	2026-01-07 18:24:49.614561	26.39	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
155	Smirnoff 1.75L	Vodka	59.58	50	\N	/data/product_images/155_Smirnoff_1.75L.jpg	2026-01-07 18:24:49.614561	44.13	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
156	Absolut 50ml	Vodka	2.94	50	\N	/data/product_images/156_Absolut_50ml.jpg	2026-01-07 18:24:49.614561	2.18	35.00	0.10	0.00	f	Premium Swedish vodka. Triple-distilled for smoothness. Clean finish, versatile for any mixed drink.
157	Absolut 375ml	Vodka	16.43	50	\N	/data/product_images/157_Absolut_375ml.jpg	2026-01-07 18:24:49.614561	12.17	35.00	0.10	0.00	f	Premium Swedish vodka. Triple-distilled for smoothness. Clean finish, versatile for any mixed drink.
158	Absolut 750ml	Vodka	30.33	50	\N	/data/product_images/158_Absolut_750ml.jpg	2026-01-07 18:24:49.614561	22.47	35.00	0.10	0.00	f	Premium Swedish vodka. Triple-distilled for smoothness. Clean finish, versatile for any mixed drink.
25	Champagne 750ml	Wine	45.00	100	https://images.unsplash.com/photo-1547595628-c61a29f496f0?w=200	/data/product_images/25_Champagne_750ml.jpg	2026-01-07 18:10:03.962356	33.33	35.00	0.10	0.00	f	Sparkling wine, celebratory and elegant
365	Barefoot Merlot 375ml	Wine - Red	10.10	50	\N	/data/product_images/365_Barefoot_Merlot_375ml.jpg	2026-01-07 18:24:49.629102	7.48	35.00	0.10	0.00	f	Smooth red wine with plum and cherry notes
366	Barefoot Merlot 750ml	Wine - Red	18.62	50	\N	/data/product_images/366_Barefoot_Merlot_750ml.jpg	2026-01-07 18:24:49.629102	13.79	35.00	0.10	0.00	f	Smooth red wine with plum and cherry notes
367	Barefoot Merlot 1.75L	Wine - Red	37.25	50	\N	/data/product_images/367_Barefoot_Merlot_1.75L.jpg	2026-01-07 18:24:49.629102	27.59	35.00	0.25	0.00	f	Smooth red wine with plum and cherry notes
377	Columbia Crest Merlot 375ml	Wine - Red	9.82	50	\N	/data/product_images/377_Columbia_Crest_Merlot_375ml.jpg	2026-01-07 18:24:49.629102	7.27	35.00	0.10	0.00	f	Smooth red wine with plum and cherry notes
460	Barefoot Bubbly 1.75L	Champagne	166.26	50	\N	/data/product_images/460_Barefoot_Bubbly_1.75L.jpg	2026-01-07 18:24:49.634988	123.16	35.00	0.25	0.00	f	California sparkling wine. Bright bubbles, fruity, celebratory.
159	Absolut 1L	Vodka	38.56	50	\N	/data/product_images/159_Absolut_1L.jpg	2026-01-07 18:24:49.614561	28.56	35.00	0.10	0.00	f	Premium Swedish vodka. Triple-distilled for smoothness. Clean finish, versatile for any mixed drink.
1102	Sol Cerveza 355ml (single)	Beer	2.49	\N	\N	\N	2026-01-08 16:29:38.329967	1.74	35.00	0.00	0.00	f	Mexican golden lager
1103	Sol Cerveza 473ml (single)	Beer	3.29	\N	\N	\N	2026-01-08 16:29:38.332318	2.30	35.00	0.00	0.00	f	Mexican golden lager
1104	Sol Cerveza 24-pack	Beer	29.99	\N	\N	\N	2026-01-08 16:29:38.332773	20.99	35.00	0.00	0.00	f	Mexican golden lager 24-pack
160	Absolut 1.75L	Vodka	61.55	50	\N	/data/product_images/160_Absolut_1.75L.jpg	2026-01-07 18:24:49.614561	45.59	35.00	0.25	0.00	f	Premium Swedish vodka. Triple-distilled for smoothness. Clean finish, versatile for any mixed drink.
161	Grey Goose 50ml	Vodka	2.87	50	\N	/data/product_images/161_Grey_Goose_50ml.jpg	2026-01-07 18:24:49.614561	2.13	35.00	0.10	0.00	f	French vodka distilled from Picardy wheat. Smooth, crisp, iconic.
162	Grey Goose 375ml	Vodka	16.27	50	\N	/data/product_images/162_Grey_Goose_375ml.jpg	2026-01-07 18:24:49.614561	12.05	35.00	0.10	0.00	f	French vodka distilled from Picardy wheat. Smooth, crisp, iconic.
163	Grey Goose 750ml	Vodka	29.64	50	\N	/data/product_images/163_Grey_Goose_750ml.jpg	2026-01-07 18:24:49.614561	21.96	35.00	0.10	0.00	f	French vodka distilled from Picardy wheat. Smooth, crisp, iconic.
1105	Breezer 355ml	Ready-To-Drink	3.99	\N	\N	\N	2026-01-08 16:31:04.679267	2.79	35.00	0.00	0.00	f	Fruit-flavored malt beverage
1106	Breezer 473ml	Ready-To-Drink	4.99	\N	\N	\N	2026-01-08 16:31:04.689092	3.49	35.00	0.00	0.00	f	Fruit-flavored malt beverage
1107	Coco Rum 750ml	Spirits	22.99	\N	\N	\N	2026-01-08 16:31:04.689618	16.09	35.00	0.00	0.00	f	Coconut-flavored rum
1108	Coco Rum 1L	Spirits	29.99	\N	\N	\N	2026-01-08 16:31:04.690983	20.99	35.00	0.00	0.00	f	Coconut-flavored rum
218	Captain Morgan 750ml	Rum	26.87	50	\N	/data/product_images/218_Captain_Morgan_750ml.jpg	2026-01-07 18:24:49.618189	19.90	35.00	0.10	0.00	f	Dark spiced rum with vanilla and cinnamon notes. Great for rum-cola.
219	Captain Morgan 1L	Rum	35.25	50	\N	/data/product_images/219_Captain_Morgan_1L.jpg	2026-01-07 18:24:49.618189	26.11	35.00	0.10	0.00	f	Dark spiced rum with vanilla and cinnamon notes. Great for rum-cola.
220	Captain Morgan 1.75L	Rum	55.37	50	\N	/data/product_images/220_Captain_Morgan_1.75L.jpg	2026-01-07 18:24:49.618189	41.01	35.00	0.25	0.00	f	Dark spiced rum with vanilla and cinnamon notes. Great for rum-cola.
221	Kraken 50ml	Rum	2.77	50	\N	/data/product_images/221_Kraken_50ml.jpg	2026-01-07 18:24:49.618189	2.05	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
222	Kraken 375ml	Rum	15.40	50	\N	/data/product_images/222_Kraken_375ml.jpg	2026-01-07 18:24:49.618189	11.41	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
223	Kraken 750ml	Rum	27.55	50	\N	/data/product_images/223_Kraken_750ml.jpg	2026-01-07 18:24:49.618189	20.41	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
224	Kraken 1L	Rum	32.80	50	\N	/data/product_images/224_Kraken_1L.jpg	2026-01-07 18:24:49.618189	24.30	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
225	Kraken 1.75L	Rum	52.18	50	\N	/data/product_images/225_Kraken_1.75L.jpg	2026-01-07 18:24:49.618189	38.65	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
226	Mount Gay 50ml	Rum	2.79	50	\N	/data/product_images/226_Mount_Gay_50ml.jpg	2026-01-07 18:24:49.618189	2.07	35.00	0.10	0.00	f	Premium rum from Barbados. Full-bodied with vanilla and oak.
227	Mount Gay 375ml	Rum	14.20	50	\N	/data/product_images/227_Mount_Gay_375ml.jpg	2026-01-07 18:24:49.618189	10.52	35.00	0.10	0.00	f	Premium rum from Barbados. Full-bodied with vanilla and oak.
228	Mount Gay 750ml	Rum	26.06	50	\N	/data/product_images/228_Mount_Gay_750ml.jpg	2026-01-07 18:24:49.618189	19.30	35.00	0.10	0.00	f	Premium rum from Barbados. Full-bodied with vanilla and oak.
229	Mount Gay 1L	Rum	32.95	50	\N	/data/product_images/229_Mount_Gay_1L.jpg	2026-01-07 18:24:49.618189	24.41	35.00	0.10	0.00	f	Premium rum from Barbados. Full-bodied with vanilla and oak.
1109	Coco Vodka 750ml	Spirits	24.99	\N	\N	\N	2026-01-08 16:31:58.007104	17.49	35.00	0.00	0.00	f	Coconut-flavored vodka
1110	Coco Vodka 1L	Spirits	31.99	\N	\N	\N	2026-01-08 16:31:58.009332	22.39	35.00	0.00	0.00	f	Coconut-flavored vodka
1111	Bud Light Chelada 355ml	Beer	2.99	\N	\N	\N	2026-01-08 16:31:58.009756	2.09	35.00	0.00	0.00	f	Bud Light with lime and spices
1112	Bud Light Chelada 473ml	Beer	3.99	\N	\N	\N	2026-01-08 16:31:58.010116	2.79	35.00	0.00	0.00	f	Bud Light with lime and spices
1113	Bud Light Hard Soda 355ml	Hard Seltzers	3.49	\N	\N	\N	2026-01-08 16:31:58.010504	2.44	35.00	0.00	0.00	f	Hard soda beverage
1114	Bud Light Hard Soda 473ml	Hard Seltzers	4.49	\N	\N	\N	2026-01-08 16:31:58.010904	3.14	35.00	0.00	0.00	f	Hard soda beverage
1115	Coors Seltzer 355ml	Hard Seltzers	2.79	\N	\N	\N	2026-01-08 16:31:58.011303	1.95	35.00	0.00	0.00	f	Crisp hard seltzer
1116	Coors Seltzer 473ml	Hard Seltzers	3.59	\N	\N	\N	2026-01-08 16:31:58.01168	2.51	35.00	0.00	0.00	f	Crisp hard seltzer
1117	Coors Seltzer 12-pack	Hard Seltzers	29.99	\N	\N	\N	2026-01-08 16:31:58.012031	20.99	35.00	0.00	0.00	f	Crisp hard seltzer 12-pack
1118	Corona Cooler 355ml	Ready-To-Drink	4.99	\N	\N	\N	2026-01-08 16:31:58.012415	3.49	35.00	0.00	0.00	f	Corona-based cooler
1119	Corona Cooler 473ml	Ready-To-Drink	6.49	\N	\N	\N	2026-01-08 16:31:58.012816	4.54	35.00	0.00	0.00	f	Corona-based cooler
1120	Vodka Water 355ml	Ready-To-Drink	5.99	\N	\N	\N	2026-01-08 16:31:58.013211	4.19	35.00	0.00	0.00	f	Vodka-infused water
171	Tito's 50ml	Vodka	2.89	50	\N	/data/product_images/171_Tito's_50ml.jpg	2026-01-07 18:24:49.614561	2.14	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
172	Tito's 375ml	Vodka	16.03	50	\N	/data/product_images/172_Tito's_375ml.jpg	2026-01-07 18:24:49.614561	11.87	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
1121	Vodka Water 473ml	Ready-To-Drink	7.49	\N	\N	\N	2026-01-08 16:31:58.013627	5.24	35.00	0.00	0.00	f	Vodka-infused water
173	Tito's 750ml	Vodka	31.05	50	\N	/data/product_images/173_Tito's_750ml.jpg	2026-01-07 18:24:49.614561	23.00	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
174	Tito's 1L	Vodka	36.80	50	\N	/data/product_images/174_Tito's_1L.jpg	2026-01-07 18:24:49.614561	27.26	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
175	Tito's 1.75L	Vodka	57.59	50	\N	/data/product_images/175_Tito's_1.75L.jpg	2026-01-07 18:24:49.614561	42.66	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
176	Ciroc 50ml	Vodka	3.13	50	\N	/data/product_images/176_Ciroc_50ml.jpg	2026-01-07 18:24:49.614561	2.32	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
177	Ciroc 375ml	Vodka	16.16	50	\N	/data/product_images/177_Ciroc_375ml.jpg	2026-01-07 18:24:49.614561	11.97	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
178	Ciroc 750ml	Vodka	29.57	50	\N	/data/product_images/178_Ciroc_750ml.jpg	2026-01-07 18:24:49.614561	21.90	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
179	Ciroc 1L	Vodka	37.82	50	\N	/data/product_images/179_Ciroc_1L.jpg	2026-01-07 18:24:49.614561	28.01	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
180	Ciroc 1.75L	Vodka	58.26	50	\N	/data/product_images/180_Ciroc_1.75L.jpg	2026-01-07 18:24:49.614561	43.16	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
181	Finlandia 50ml	Vodka	2.92	50	\N	/data/product_images/181_Finlandia_50ml.jpg	2026-01-07 18:24:49.614561	2.16	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
182	Finlandia 375ml	Vodka	15.68	50	\N	/data/product_images/182_Finlandia_375ml.jpg	2026-01-07 18:24:49.614561	11.61	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
183	Finlandia 750ml	Vodka	30.20	50	\N	/data/product_images/183_Finlandia_750ml.jpg	2026-01-07 18:24:49.614561	22.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
184	Finlandia 1L	Vodka	37.51	50	\N	/data/product_images/184_Finlandia_1L.jpg	2026-01-07 18:24:49.614561	27.79	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
185	Finlandia 1.75L	Vodka	61.68	50	\N	/data/product_images/185_Finlandia_1.75L.jpg	2026-01-07 18:24:49.614561	45.69	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
186	Skyy 50ml	Vodka	3.14	50	\N	/data/product_images/186_Skyy_50ml.jpg	2026-01-07 18:24:49.614561	2.33	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
187	Skyy 375ml	Vodka	16.90	50	\N	/data/product_images/187_Skyy_375ml.jpg	2026-01-07 18:24:49.614561	12.52	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
188	Skyy 750ml	Vodka	28.87	50	\N	/data/product_images/188_Skyy_750ml.jpg	2026-01-07 18:24:49.614561	21.39	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
189	Skyy 1L	Vodka	36.12	50	\N	/data/product_images/189_Skyy_1L.jpg	2026-01-07 18:24:49.614561	26.76	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
231	Sailor Jerry 50ml	Rum	2.74	50	\N	/data/product_images/231_Sailor_Jerry_50ml.jpg	2026-01-07 18:24:49.618189	2.03	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
232	Sailor Jerry 375ml	Rum	14.56	50	\N	/data/product_images/232_Sailor_Jerry_375ml.jpg	2026-01-07 18:24:49.618189	10.79	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
233	Sailor Jerry 750ml	Rum	28.17	50	\N	/data/product_images/233_Sailor_Jerry_750ml.jpg	2026-01-07 18:24:49.618189	20.87	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
234	Sailor Jerry 1L	Rum	35.30	50	\N	/data/product_images/234_Sailor_Jerry_1L.jpg	2026-01-07 18:24:49.618189	26.15	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
235	Sailor Jerry 1.75L	Rum	54.84	50	\N	/data/product_images/235_Sailor_Jerry_1.75L.jpg	2026-01-07 18:24:49.618189	40.62	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
236	Myers's 50ml	Rum	2.66	50	\N	/data/product_images/236_Myers's_50ml.jpg	2026-01-07 18:24:49.618189	1.97	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
237	Myers's 375ml	Rum	14.74	50	\N	/data/product_images/237_Myers's_375ml.jpg	2026-01-07 18:24:49.618189	10.92	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
238	Myers's 750ml	Rum	28.00	50	\N	/data/product_images/238_Myers's_750ml.jpg	2026-01-07 18:24:49.618189	20.74	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
239	Myers's 1L	Rum	32.74	50	\N	/data/product_images/239_Myers's_1L.jpg	2026-01-07 18:24:49.618189	24.25	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
240	Myers's 1.75L	Rum	54.73	50	\N	/data/product_images/240_Myers's_1.75L.jpg	2026-01-07 18:24:49.618189	40.54	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
1122	Epitaph Blue Gin 750ml	Spirits	39.99	\N	\N	\N	2026-01-08 16:34:07.679932	27.99	35.00	0.00	0.00	f	Troubled Monk craft gin
1123	Epitaph Gin 375ml	Spirits	21.99	\N	\N	\N	2026-01-08 16:34:07.682452	15.39	35.00	0.00	0.00	f	Troubled Monk craft gin
1124	Long Drink 355ml	Ready-To-Drink	4.49	\N	\N	\N	2026-01-08 16:35:49.810145	3.14	35.00	0.00	0.00	f	Finnish gin & grapefruit soda
1125	Long Drink 473ml	Ready-To-Drink	5.99	\N	\N	\N	2026-01-08 16:35:49.812746	4.19	35.00	0.00	0.00	f	Finnish gin & grapefruit soda
1126	Tequila Smash Cooler 355ml	Ready-To-Drink	6.99	\N	\N	\N	2026-01-08 16:35:49.813523	4.89	35.00	0.00	0.00	f	Tequila-based cooler
1127	Tequila Smash Cooler 473ml	Ready-To-Drink	8.99	\N	\N	\N	2026-01-08 16:35:49.815078	6.29	35.00	0.00	0.00	f	Tequila-based cooler
1128	Happy Dad Hard Seltzer 355ml	Hard Seltzers	3.99	\N	\N	\N	2026-01-08 16:35:49.815572	2.79	35.00	0.00	0.00	f	Hard seltzer
1129	Happy Dad Hard Seltzer 473ml	Hard Seltzers	4.99	\N	\N	\N	2026-01-08 16:35:49.816106	3.49	35.00	0.00	0.00	f	Hard seltzer
1130	Happy Dad Hard Seltzer 12-pack	Hard Seltzers	34.99	\N	\N	\N	2026-01-08 16:35:49.816547	24.49	35.00	0.00	0.00	f	Hard seltzer 12-pack
1131	Happy Mom Wine Cocktail 355ml	Ready-To-Drink	4.99	\N	\N	\N	2026-01-08 16:35:49.817104	3.49	35.00	0.00	0.00	f	Wine-based cocktail
1132	Happy Mom Wine Cocktail 473ml	Ready-To-Drink	6.49	\N	\N	\N	2026-01-08 16:35:49.817553	4.54	35.00	0.00	0.00	f	Wine-based cocktail
333	Sauza 750ml	Tequila	34.08	50	\N	/data/product_images/333_Sauza_750ml.jpg	2026-01-07 18:24:49.626279	25.24	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
334	Sauza 1L	Tequila	42.78	50	\N	/data/product_images/334_Sauza_1L.jpg	2026-01-07 18:24:49.626279	31.69	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
335	Sauza 1.75L	Tequila	70.75	50	\N	/data/product_images/335_Sauza_1.75L.jpg	2026-01-07 18:24:49.626279	52.41	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
336	Tres Generaciones 50ml	Tequila	3.37	50	\N	/data/product_images/336_Tres_Generaciones_50ml.jpg	2026-01-07 18:24:49.626279	2.50	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
1133	Ranch Water 355ml	Ready-To-Drink	4.99	\N	\N	\N	2026-01-08 16:38:09.06644	3.49	35.00	0.00	0.00	f	Tequila lime sparkling water
1134	Ranch Water 473ml	Ready-To-Drink	6.49	\N	\N	\N	2026-01-08 16:38:09.0699	4.54	35.00	0.00	0.00	f	Tequila lime sparkling water
1135	Malibu Coconut Rum 50ml	Spirits	2.99	\N	\N	\N	2026-01-08 16:38:09.070471	2.09	35.00	0.00	0.00	f	Coconut rum
1136	Malibu Coconut Rum 375ml	Spirits	16.99	\N	\N	\N	2026-01-08 16:38:09.071142	11.89	35.00	0.00	0.00	f	Coconut rum
1137	Malibu Coconut Rum 750ml	Spirits	27.99	\N	\N	\N	2026-01-08 16:38:09.071474	19.59	35.00	0.00	0.00	f	Coconut rum
1138	Malibu Coconut Rum 1L	Spirits	35.99	\N	\N	\N	2026-01-08 16:38:09.072002	25.19	35.00	0.00	0.00	f	Coconut rum
1139	Malibu Coconut Rum 1.75L	Spirits	54.99	\N	\N	\N	2026-01-08 16:38:09.072502	38.49	35.00	0.00	0.00	f	Coconut rum
1140	AGD Classic Lager 355ml	Beer	2.49	\N	\N	\N	2026-01-08 16:44:46.579262	1.74	35.00	0.00	0.00	f	Alberta Genuine Draft lager
1141	AGD Classic Lager 473ml	Beer	3.29	\N	\N	\N	2026-01-08 16:44:46.581643	2.30	35.00	0.00	0.00	f	Alberta Genuine Draft lager
1142	AGD Classic Lager 6-pack	Beer	12.99	\N	\N	\N	2026-01-08 16:44:46.582058	9.09	35.00	0.00	0.00	f	Alberta Genuine Draft 6-pack
1143	Sawback East Coast Hazy Pale Ale 473ml	Beer	5.99	\N	\N	\N	2026-01-08 16:44:46.582438	4.19	35.00	0.00	0.00	f	Red Deer craft brewery - Session IPA
1144	Sawback Wild West Coast IPA 473ml	Beer	6.49	\N	\N	\N	2026-01-08 16:44:46.5828	4.54	35.00	0.00	0.00	f	Red Deer craft brewery - Brett beer
1145	Sawback Irish Red Ale 473ml	Beer	5.99	\N	\N	\N	2026-01-08 16:44:46.58311	4.19	35.00	0.00	0.00	f	Red Deer craft brewery - Irish red ale
1146	Sawback Passion Fruit Sour 473ml	Beer	6.99	\N	\N	\N	2026-01-08 16:44:46.583441	4.89	35.00	0.00	0.00	f	Red Deer craft brewery - Fruited sour
1147	Sawback Hazy Blonde Ale 473ml	Beer	5.99	\N	\N	\N	2026-01-08 16:44:46.583803	4.19	35.00	0.00	0.00	f	Red Deer craft brewery - Blonde ale
1148	Sawback India Dark Ale 473ml	Beer	6.49	\N	\N	\N	2026-01-08 16:44:46.584141	4.54	35.00	0.00	0.00	f	Red Deer craft brewery - Specialty IPA
1149	Sawback Saison No.1 473ml	Beer	6.49	\N	\N	\N	2026-01-08 16:44:46.584441	4.54	35.00	0.00	0.00	f	Red Deer craft brewery - Belgian saison
1150	Sawback Wild Sour Saison 473ml	Beer	6.99	\N	\N	\N	2026-01-08 16:44:46.584764	4.89	35.00	0.00	0.00	f	Red Deer craft brewery - Sour saison
1151	Sawback West Coast IPA 473ml	Beer	6.49	\N	\N	\N	2026-01-08 16:44:46.585121	4.54	35.00	0.00	0.00	f	Red Deer craft brewery - West coast IPA
1152	Alley Kat Full Moon Pale Ale 473ml	Beer	5.49	\N	\N	\N	2026-01-08 16:47:59.536068	3.84	35.00	0.00	0.00	f	Edmonton craft brewery - Pale ale
1153	Alley Kat Aprikat Apricot Ale 473ml	Beer	5.49	\N	\N	\N	2026-01-08 16:47:59.538422	3.84	35.00	0.00	0.00	f	Edmonton craft brewery - Fruit ale
1154	Alley Kat Charlie Flint's Lager 473ml	Beer	5.49	\N	\N	\N	2026-01-08 16:47:59.539073	3.84	35.00	0.00	0.00	f	Edmonton craft brewery - Lager
1155	Alley Kat Amber Ale 473ml	Beer	5.49	\N	\N	\N	2026-01-08 16:47:59.539837	3.84	35.00	0.00	0.00	f	Edmonton craft brewery - Amber ale
1156	Alley Kat Dragon Series Double IPA 473ml	Beer	6.49	\N	\N	\N	2026-01-08 16:47:59.540405	4.54	35.00	0.00	0.00	f	Edmonton craft brewery - Double IPA
1157	Alley Kat Full Moon Pale Ale 6-pack	Beer	14.99	\N	\N	\N	2026-01-08 16:47:59.540825	10.49	35.00	0.00	0.00	f	Edmonton craft brewery 6-pack
430	Barefoot Moscato 1.75L	Wine - White	33.04	50	\N	/data/product_images/430_Barefoot_Moscato_1.75L.jpg	2026-01-07 18:24:49.631936	24.47	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
431	Dom Pérignon 375ml	Champagne	44.37	50	\N	/data/product_images/431_Dom_Pérignon_375ml.jpg	2026-01-07 18:24:49.634988	32.87	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
432	Dom Pérignon 750ml	Champagne	78.68	50	\N	/data/product_images/432_Dom_Pérignon_750ml.jpg	2026-01-07 18:24:49.634988	58.28	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
433	Dom Pérignon 1.75L	Champagne	152.64	50	\N	/data/product_images/433_Dom_Pérignon_1.75L.jpg	2026-01-07 18:24:49.634988	113.07	35.00	0.25	0.00	f	Champagne. Elegant, celebratory sparkling wine.
434	Moët & Chandon 375ml	Champagne	43.52	50	\N	/data/product_images/434_Moët_&_Chandon_375ml.jpg	2026-01-07 18:24:49.634988	32.24	35.00	0.10	0.00	f	Champagne. Elegant, celebratory sparkling wine.
1158	Blind Man Brewing Session 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.547402	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Blonde ale with citrus notes
1159	Blind Man Brewing Longshadows IPA 473ml	Beer	5.99	\N	\N	\N	2026-01-08 17:00:32.549816	4.19	35.00	0.00	0.00	f	Lacombe craft brewery - West Coast IPA
1160	Blind Man Brewing Five of Diamonds Pilsner 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.551138	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Clean pilsner
1161	Blind Man Brewing Dwarf Sour Cherry 473ml	Beer	6.49	\N	\N	\N	2026-01-08 17:00:32.55197	4.54	35.00	0.00	0.00	f	Lacombe craft brewery - Award-winning sour
1162	Blind Man Brewing Kettle Sour 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.552856	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Tart wheat ale
1163	Blind Man Brewing Dream Machine Mexican Lager 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.553321	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Light lager
1164	Blind Man Brewing Dark Lager 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.55376	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - German dark lager
1165	Blind Man Brewing Triphammer Robust Porter 473ml	Beer	5.99	\N	\N	\N	2026-01-08 17:00:32.554251	4.19	35.00	0.00	0.00	f	Lacombe craft brewery - Porter
1166	Blind Man Brewing Ichorous Imperial Stout 473ml	Beer	6.99	\N	\N	\N	2026-01-08 17:00:32.554692	4.89	35.00	0.00	0.00	f	Lacombe craft brewery - Imperial stout
1167	Blind Man Brewing New England Pale Ale 473ml	Beer	5.99	\N	\N	\N	2026-01-08 17:00:32.555165	4.19	35.00	0.00	0.00	f	Lacombe craft brewery - Juicy hazy pale ale
1168	Blind Man Brewing May Long Double IPA 473ml	Beer	6.49	\N	\N	\N	2026-01-08 17:00:32.555555	4.54	35.00	0.00	0.00	f	Lacombe craft brewery - Big double IPA
1169	Blind Man Brewing Coffee Stout 473ml	Beer	5.99	\N	\N	\N	2026-01-08 17:00:32.555992	4.19	35.00	0.00	0.00	f	Lacombe craft brewery - Coffee stout
1170	Blind Man Brewing Shelter Belt Blonde Ale 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.556433	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Blonde ale
1171	Blind Man Brewing Kuyt Wheat Beer 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.556826	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Dutch wheat beer
1172	Blind Man Brewing Czech Pale Lager 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.557227	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Wood-aged lager
1173	Blind Man Brewing Radler 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.557629	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Grapefruit radler
1174	Blind Man Brewing Lil Buzz Honey Lager 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.558063	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Honey lager
461	Budweiser 355ml (single)	Beer	2.52	50	\N	/data/product_images/461_Budweiser_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.87	35.00	0.10	0.00	f	American lager with subtle sweetness
1175	Blind Man Brewing Raspberry Light Ale 473ml	Beer	5.49	\N	\N	\N	2026-01-08 17:00:32.558458	3.84	35.00	0.00	0.00	f	Lacombe craft brewery - Raspberry ale
462	Budweiser 24-pack	Beer	32.38	50	\N	/data/product_images/462_Budweiser_24-pack.jpg	2026-01-07 18:24:49.636927	23.99	35.00	2.40	0.00	f	American lager with subtle sweetness
1176	Blind Man Brewing Wander Hop Water 355ml	Non-Alcoholic	3.99	\N	\N	\N	2026-01-08 17:00:32.558871	2.79	35.00	0.00	0.00	f	Lacombe - Hop water, zero alcohol
1177	Blind Man Brewing Wander Tropical Hop Water 355ml	Non-Alcoholic	3.99	\N	\N	\N	2026-01-08 17:00:32.559313	2.79	35.00	0.00	0.00	f	Lacombe - Tropical hop water, zero alcohol
1178	Blind Man Brewing Perepllut Barley Wine 473ml	Beer	7.99	\N	\N	\N	2026-01-08 17:00:32.559696	5.59	35.00	0.00	0.00	f	Lacombe craft brewery - Barley wine
1179	Blind Man Brewing Barrel-Aged Brett 24-2 Stock Ale 473ml	Beer	7.99	\N	\N	\N	2026-01-08 17:00:32.560109	5.59	35.00	0.00	0.00	f	Lacombe craft brewery - Barrel-aged ale
463	Bud Light 355ml (single)	Beer	2.50	50	\N	/data/product_images/463_Bud_Light_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.85	35.00	0.10	0.00	f	Light American lager, smooth and refreshing
464	Bud Light 24-pack	Beer	30.67	50	\N	/data/product_images/464_Bud_Light_24-pack.jpg	2026-01-07 18:24:49.636927	22.72	35.00	2.40	0.00	f	Light American lager, smooth and refreshing
849	Ouzo 1L	Liqueurs	45.75	50	\N	/data/product_images/849_Ouzo_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
465	Coors Light 355ml (single)	Beer	2.55	50	\N	/data/product_images/465_Coors_Light_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.89	35.00	0.10	0.00	f	Light, crisp American lager
466	Coors Light 24-pack	Beer	32.25	50	\N	/data/product_images/466_Coors_Light_24-pack.jpg	2026-01-07 18:24:49.636927	23.89	35.00	2.40	0.00	f	Light, crisp American lager
467	Miller Lite 355ml (single)	Beer	2.62	50	\N	/data/product_images/467_Miller_Lite_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.94	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
468	Miller Lite 24-pack	Beer	30.43	50	\N	/data/product_images/468_Miller_Lite_24-pack.jpg	2026-01-07 18:24:49.636927	22.54	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
469	Corona 355ml (single)	Beer	2.54	50	\N	/data/product_images/469_Corona_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.88	35.00	0.10	0.00	f	Light, crisp Mexican lager with citrus notes
46	Macallan Macallan Whiskey	Spirits	120.00	50	\N	/data/product_images/46_Macallan_Macallan_Whiskey.jpg	2026-01-07 18:15:08.023848	88.89	35.00	0.10	0.00	f	Aged spirit with complex oak and grain flavors
470	Corona 24-pack	Beer	33.37	50	\N	/data/product_images/470_Corona_24-pack.jpg	2026-01-07 18:24:49.636927	24.72	35.00	2.40	0.00	f	Light, crisp Mexican lager with citrus notes
471	Heineken 355ml (single)	Beer	2.41	50	\N	/data/product_images/471_Heineken_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.79	35.00	0.10	0.00	f	Classic Dutch pilsner with balanced hop bitterness
472	Heineken 24-pack	Beer	32.40	50	\N	/data/product_images/472_Heineken_24-pack.jpg	2026-01-07 18:24:49.636927	24.00	35.00	2.40	0.00	f	Classic Dutch pilsner with balanced hop bitterness
473	Guinness 355ml (single)	Beer	2.62	50	\N	/data/product_images/473_Guinness_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.94	35.00	0.10	0.00	f	Rich, creamy Irish stout with coffee and chocolate notes
474	Guinness 24-pack	Beer	30.88	50	\N	/data/product_images/474_Guinness_24-pack.jpg	2026-01-07 18:24:49.636927	22.87	35.00	2.40	0.00	f	Rich, creamy Irish stout with coffee and chocolate notes
475	Stella Artois 355ml (single)	Beer	2.52	50	\N	/data/product_images/475_Stella_Artois_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.87	35.00	0.10	0.00	f	Belgian lager. Smooth, balanced, slightly fruity.
476	Stella Artois 24-pack	Beer	31.73	50	\N	/data/product_images/476_Stella_Artois_24-pack.jpg	2026-01-07 18:24:49.636927	23.50	35.00	2.40	0.00	f	Belgian lager. Smooth, balanced, slightly fruity.
477	Peroni 355ml (single)	Beer	2.47	50	\N	/data/product_images/477_Peroni_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.83	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
478	Peroni 24-pack	Beer	31.83	50	\N	/data/product_images/478_Peroni_24-pack.jpg	2026-01-07 18:24:49.636927	23.58	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
479	Modelo 355ml (single)	Beer	2.44	50	\N	/data/product_images/479_Modelo_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.81	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
480	Modelo 24-pack	Beer	33.36	50	\N	/data/product_images/480_Modelo_24-pack.jpg	2026-01-07 18:24:49.636927	24.71	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
481	Dos Equis 355ml (single)	Beer	2.46	50	\N	/data/product_images/481_Dos_Equis_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.82	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
482	Dos Equis 24-pack	Beer	31.93	50	\N	/data/product_images/482_Dos_Equis_24-pack.jpg	2026-01-07 18:24:49.636927	23.65	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
483	Labatt Blue 355ml (single)	Beer	2.52	50	\N	/data/product_images/483_Labatt_Blue_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.87	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
484	Labatt Blue 24-pack	Beer	31.33	50	\N	/data/product_images/484_Labatt_Blue_24-pack.jpg	2026-01-07 18:24:49.636927	23.21	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
485	Molson Canadian 355ml (single)	Beer	2.59	50	\N	/data/product_images/485_Molson_Canadian_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.92	35.00	0.10	0.00	f	Canadian lager. Light, crisp, easy-drinking.
486	Molson Canadian 24-pack	Beer	32.82	50	\N	/data/product_images/486_Molson_Canadian_24-pack.jpg	2026-01-07 18:24:49.636927	24.31	35.00	2.40	0.00	f	Canadian lager. Light, crisp, easy-drinking.
487	Blue Moon 355ml (single)	Beer	2.57	50	\N	/data/product_images/487_Blue_Moon_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.90	35.00	0.10	0.00	f	American wheat ale. Smooth, with orange citrus notes.
488	Blue Moon 24-pack	Beer	32.79	50	\N	/data/product_images/488_Blue_Moon_24-pack.jpg	2026-01-07 18:24:49.636927	24.29	35.00	2.40	0.00	f	American wheat ale. Smooth, with orange citrus notes.
489	Sam Adams 355ml (single)	Beer	2.57	50	\N	/data/product_images/489_Sam_Adams_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.90	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
48	Perrier Perrier	Water	4.00	50	\N	/data/product_images/48_Perrier_Perrier.jpg	2026-01-07 18:15:08.023848	2.96	35.00	0.10	0.00	f	\N
490	Sam Adams 24-pack	Beer	31.33	50	\N	/data/product_images/490_Sam_Adams_24-pack.jpg	2026-01-07 18:24:49.636927	23.21	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
491	Craft IPA Mix 355ml (single)	Beer	2.53	50	\N	/data/product_images/491_Craft_IPA_Mix_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.87	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
492	Craft IPA Mix 24-pack	Beer	33.59	50	\N	/data/product_images/492_Craft_IPA_Mix_24-pack.jpg	2026-01-07 18:24:49.636927	24.88	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
493	Pale Ale 355ml (single)	Beer	2.44	50	\N	/data/product_images/493_Pale_Ale_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.81	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
494	Pale Ale 24-pack	Beer	32.20	50	\N	/data/product_images/494_Pale_Ale_24-pack.jpg	2026-01-07 18:24:49.636927	23.85	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
495	Porter 355ml (single)	Beer	2.57	50	\N	/data/product_images/495_Porter_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.90	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
496	Porter 24-pack	Beer	31.14	50	\N	/data/product_images/496_Porter_24-pack.jpg	2026-01-07 18:24:49.636927	23.07	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
497	Stout 355ml (single)	Beer	2.62	50	\N	/data/product_images/497_Stout_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.94	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
498	Stout 24-pack	Beer	32.18	50	\N	/data/product_images/498_Stout_24-pack.jpg	2026-01-07 18:24:49.636927	23.84	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
499	Belgian Ale 355ml (single)	Beer	2.54	50	\N	/data/product_images/499_Belgian_Ale_355ml_(single).jpg	2026-01-07 18:24:49.636927	1.88	35.00	0.10	0.00	f	Quality beer. Crisp and refreshing.
500	Belgian Ale 24-pack	Beer	32.56	50	\N	/data/product_images/500_Belgian_Ale_24-pack.jpg	2026-01-07 18:24:49.636927	24.12	35.00	2.40	0.00	f	Quality beer. Crisp and refreshing.
501	Bushmills 50ml	Whiskey	3.80	50	\N	/data/product_images/501_Bushmills_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
502	Bushmills 375ml	Whiskey	20.90	50	\N	/data/product_images/502_Bushmills_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
503	Bushmills 750ml	Whiskey	38.00	50	\N	/data/product_images/503_Bushmills_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
504	Bushmills 1L	Whiskey	47.50	50	\N	/data/product_images/504_Bushmills_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
505	Bushmills 1.75L	Whiskey	76.00	50	\N	/data/product_images/505_Bushmills_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
506	Glenmorangie 50ml	Whiskey	3.80	50	\N	/data/product_images/506_Glenmorangie_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
507	Glenmorangie 375ml	Whiskey	20.90	50	\N	/data/product_images/507_Glenmorangie_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
508	Glenmorangie 750ml	Whiskey	38.00	50	\N	/data/product_images/508_Glenmorangie_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
509	Glenmorangie 1L	Whiskey	47.50	50	\N	/data/product_images/509_Glenmorangie_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
510	Glenmorangie 1.75L	Whiskey	76.00	50	\N	/data/product_images/510_Glenmorangie_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
511	Glenlivet 50ml	Whiskey	3.80	50	\N	/data/product_images/511_Glenlivet_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
512	Glenlivet 375ml	Whiskey	20.90	50	\N	/data/product_images/512_Glenlivet_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
513	Glenlivet 750ml	Whiskey	38.00	50	\N	/data/product_images/513_Glenlivet_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
52	Corona Beer - Premium Lager	beer	6.00	75	\N	/data/product_images/52_Corona_Beer_-_Premium_Lager.jpg	2026-01-07 18:21:51.425497	4.44	35.00	0.10	0.00	f	Light, crisp Mexican lager with citrus notes
549	Macallan Single Malt 1L	Whiskey	47.50	50	\N	/data/product_images/549_Macallan_Single_Malt_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
54	Starbucks Coffee - Premium	non-alcoholic	5.00	75	\N	/data/product_images/54_Starbucks_Coffee_-_Premium.jpg	2026-01-07 18:21:51.425497	3.70	35.00	0.10	0.00	f	\N
550	Macallan Single Malt 1.75L	Whiskey	76.00	50	\N	/data/product_images/550_Macallan_Single_Malt_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
551	Bowmore 50ml	Whiskey	3.80	50	\N	/data/product_images/551_Bowmore_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
552	Bowmore 375ml	Whiskey	20.90	50	\N	/data/product_images/552_Bowmore_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
553	Bowmore 750ml	Whiskey	38.00	50	\N	/data/product_images/553_Bowmore_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
554	Bowmore 1L	Whiskey	47.50	50	\N	/data/product_images/554_Bowmore_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
555	Bowmore 1.75L	Whiskey	76.00	50	\N	/data/product_images/555_Bowmore_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
557	Laphroaig 375ml	Whiskey	20.90	50	\N	/data/product_images/557_Laphroaig_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
558	Laphroaig 750ml	Whiskey	38.00	50	\N	/data/product_images/558_Laphroaig_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
559	Laphroaig 1L	Whiskey	47.50	50	\N	/data/product_images/559_Laphroaig_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
560	Laphroaig 1.75L	Whiskey	76.00	50	\N	/data/product_images/560_Laphroaig_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
561	Ardbeg 50ml	Whiskey	3.80	50	\N	/data/product_images/561_Ardbeg_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
562	Ardbeg 375ml	Whiskey	20.90	50	\N	/data/product_images/562_Ardbeg_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
563	Ardbeg 750ml	Whiskey	38.00	50	\N	/data/product_images/563_Ardbeg_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
564	Ardbeg 1L	Whiskey	47.50	50	\N	/data/product_images/564_Ardbeg_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
565	Ardbeg 1.75L	Whiskey	76.00	50	\N	/data/product_images/565_Ardbeg_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
566	Springbank 50ml	Whiskey	3.80	50	\N	/data/product_images/566_Springbank_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
567	Springbank 375ml	Whiskey	20.90	50	\N	/data/product_images/567_Springbank_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
568	Springbank 750ml	Whiskey	38.00	50	\N	/data/product_images/568_Springbank_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
569	Springbank 1L	Whiskey	47.50	50	\N	/data/product_images/569_Springbank_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
56	Tropicana Juice - Orange	non-alcoholic	4.00	75	\N	/data/product_images/56_Tropicana_Juice_-_Orange.jpg	2026-01-07 18:21:51.425497	2.96	35.00	0.10	0.00	f	\N
570	Springbank 1.75L	Whiskey	76.00	50	\N	/data/product_images/570_Springbank_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
571	Dalmore 50ml	Whiskey	3.80	50	\N	/data/product_images/571_Dalmore_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
572	Dalmore 375ml	Whiskey	20.90	50	\N	/data/product_images/572_Dalmore_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
573	Dalmore 750ml	Whiskey	38.00	50	\N	/data/product_images/573_Dalmore_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
574	Dalmore 1L	Whiskey	47.50	50	\N	/data/product_images/574_Dalmore_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
575	Dalmore 1.75L	Whiskey	76.00	50	\N	/data/product_images/575_Dalmore_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
576	Premium Vodka Selection 50ml	Vodka	3.20	50	\N	/data/product_images/576_Premium_Vodka_Selection_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Neutral spirit, versatile for mixed drinks
577	Premium Vodka Selection 375ml	Vodka	17.60	50	\N	/data/product_images/577_Premium_Vodka_Selection_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Neutral spirit, versatile for mixed drinks
578	Premium Vodka Selection 750ml	Vodka	32.00	50	\N	/data/product_images/578_Premium_Vodka_Selection_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Neutral spirit, versatile for mixed drinks
579	Premium Vodka Selection 1L	Vodka	40.00	50	\N	/data/product_images/579_Premium_Vodka_Selection_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Neutral spirit, versatile for mixed drinks
580	Premium Vodka Selection 1.75L	Vodka	64.00	50	\N	/data/product_images/580_Premium_Vodka_Selection_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Neutral spirit, versatile for mixed drinks
581	Crystal Head 50ml	Vodka	3.20	50	\N	/data/product_images/581_Crystal_Head_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
582	Crystal Head 375ml	Vodka	17.60	50	\N	/data/product_images/582_Crystal_Head_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
583	Crystal Head 750ml	Vodka	32.00	50	\N	/data/product_images/583_Crystal_Head_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
584	Crystal Head 1L	Vodka	40.00	50	\N	/data/product_images/584_Crystal_Head_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
585	Crystal Head 1.75L	Vodka	64.00	50	\N	/data/product_images/585_Crystal_Head_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
586	Chopin 50ml	Vodka	3.20	50	\N	/data/product_images/586_Chopin_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
587	Chopin 375ml	Vodka	17.60	50	\N	/data/product_images/587_Chopin_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
588	Chopin 750ml	Vodka	32.00	50	\N	/data/product_images/588_Chopin_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
589	Chopin 1L	Vodka	40.00	50	\N	/data/product_images/589_Chopin_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
58	Perrier Water - Sparkling	non-alcoholic	3.00	75	\N	/data/product_images/58_Perrier_Water_-_Sparkling.jpg	2026-01-07 18:21:51.425497	2.22	35.00	0.10	0.00	f	\N
590	Chopin 1.75L	Vodka	64.00	50	\N	/data/product_images/590_Chopin_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
591	Zubrowka 50ml	Vodka	3.20	50	\N	/data/product_images/591_Zubrowka_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
592	Zubrowka 375ml	Vodka	17.60	50	\N	/data/product_images/592_Zubrowka_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
593	Zubrowka 750ml	Vodka	32.00	50	\N	/data/product_images/593_Zubrowka_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
594	Zubrowka 1L	Vodka	40.00	50	\N	/data/product_images/594_Zubrowka_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
595	Zubrowka 1.75L	Vodka	64.00	50	\N	/data/product_images/595_Zubrowka_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
596	Russian Standard 50ml	Vodka	3.20	50	\N	/data/product_images/596_Russian_Standard_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
597	Russian Standard 375ml	Vodka	17.60	50	\N	/data/product_images/597_Russian_Standard_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
598	Russian Standard 750ml	Vodka	32.00	50	\N	/data/product_images/598_Russian_Standard_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
599	Russian Standard 1L	Vodka	40.00	50	\N	/data/product_images/599_Russian_Standard_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
600	Russian Standard 1.75L	Vodka	64.00	50	\N	/data/product_images/600_Russian_Standard_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
601	Eristoff 50ml	Vodka	3.20	50	\N	/data/product_images/601_Eristoff_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
602	Eristoff 375ml	Vodka	17.60	50	\N	/data/product_images/602_Eristoff_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
603	Eristoff 750ml	Vodka	32.00	50	\N	/data/product_images/603_Eristoff_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
604	Eristoff 1L	Vodka	40.00	50	\N	/data/product_images/604_Eristoff_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
605	Eristoff 1.75L	Vodka	64.00	50	\N	/data/product_images/605_Eristoff_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
606	Popov 50ml	Vodka	3.20	50	\N	/data/product_images/606_Popov_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
607	Popov 375ml	Vodka	17.60	50	\N	/data/product_images/607_Popov_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
608	Popov 750ml	Vodka	32.00	50	\N	/data/product_images/608_Popov_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
609	Popov 1L	Vodka	40.00	50	\N	/data/product_images/609_Popov_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
60	Evian Water - Still	non-alcoholic	2.50	75	\N	/data/product_images/60_Evian_Water_-_Still.jpg	2026-01-07 18:21:51.425497	1.85	35.00	0.10	0.00	f	\N
610	Popov 1.75L	Vodka	64.00	50	\N	/data/product_images/610_Popov_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
611	Barton 50ml	Vodka	3.20	50	\N	/data/product_images/611_Barton_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
612	Barton 375ml	Vodka	17.60	50	\N	/data/product_images/612_Barton_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
613	Barton 750ml	Vodka	32.00	50	\N	/data/product_images/613_Barton_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
614	Barton 1L	Vodka	40.00	50	\N	/data/product_images/614_Barton_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
615	Barton 1.75L	Vodka	64.00	50	\N	/data/product_images/615_Barton_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
616	Burnetts 50ml	Vodka	3.20	50	\N	/data/product_images/616_Burnetts_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
617	Burnetts 375ml	Vodka	17.60	50	\N	/data/product_images/617_Burnetts_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
618	Burnetts 750ml	Vodka	32.00	50	\N	/data/product_images/618_Burnetts_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
619	Burnetts 1L	Vodka	40.00	50	\N	/data/product_images/619_Burnetts_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
620	Burnetts 1.75L	Vodka	64.00	50	\N	/data/product_images/620_Burnetts_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
621	Gilbeys 50ml	Vodka	3.20	50	\N	/data/product_images/621_Gilbeys_50ml.jpg	2026-01-07 18:25:13.613795	2.37	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
622	Gilbeys 375ml	Vodka	17.60	50	\N	/data/product_images/622_Gilbeys_375ml.jpg	2026-01-07 18:25:13.613795	13.04	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
623	Gilbeys 750ml	Vodka	32.00	50	\N	/data/product_images/623_Gilbeys_750ml.jpg	2026-01-07 18:25:13.613795	23.70	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
624	Gilbeys 1L	Vodka	40.00	50	\N	/data/product_images/624_Gilbeys_1L.jpg	2026-01-07 18:25:13.613795	29.63	35.00	0.10	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
625	Gilbeys 1.75L	Vodka	64.00	50	\N	/data/product_images/625_Gilbeys_1.75L.jpg	2026-01-07 18:25:13.613795	47.41	35.00	0.25	0.00	f	Premium vodka. Clean, versatile spirit for mixed drinks and cocktails.
626	Diplomatico 50ml	Rum	3.20	50	\N	/data/product_images/626_Diplomatico_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
627	Diplomatico 375ml	Rum	17.60	50	\N	/data/product_images/627_Diplomatico_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
628	Diplomatico 750ml	Rum	32.00	50	\N	/data/product_images/628_Diplomatico_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
629	Diplomatico 1L	Rum	40.00	50	\N	/data/product_images/629_Diplomatico_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
62	Godiva Chocolate - Artisan	snacks	12.00	75	\N	/data/product_images/62_Godiva_Chocolate_-_Artisan.jpg	2026-01-07 18:21:51.425497	8.89	35.00	0.10	0.00	f	\N
630	Diplomatico 1.75L	Rum	64.00	50	\N	/data/product_images/630_Diplomatico_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
631	Ron Zacapa 50ml	Rum	3.20	50	\N	/data/product_images/631_Ron_Zacapa_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
632	Ron Zacapa 375ml	Rum	17.60	50	\N	/data/product_images/632_Ron_Zacapa_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
633	Ron Zacapa 750ml	Rum	32.00	50	\N	/data/product_images/633_Ron_Zacapa_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
318	Don Julio 750ml	Tequila	34.38	50	\N	/data/product_images/318_Don_Julio_750ml.jpg	2026-01-07 18:24:49.626279	25.47	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
319	Don Julio 1L	Tequila	43.73	50	\N	/data/product_images/319_Don_Julio_1L.jpg	2026-01-07 18:24:49.626279	32.39	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
320	Don Julio 1.75L	Tequila	68.03	50	\N	/data/product_images/320_Don_Julio_1.75L.jpg	2026-01-07 18:24:49.626279	50.39	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
321	Cointreau 50ml	Tequila	3.45	50	\N	/data/product_images/321_Cointreau_50ml.jpg	2026-01-07 18:24:49.626279	2.56	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
322	Cointreau 375ml	Tequila	19.16	50	\N	/data/product_images/322_Cointreau_375ml.jpg	2026-01-07 18:24:49.626279	14.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
323	Cointreau 750ml	Tequila	36.51	50	\N	/data/product_images/323_Cointreau_750ml.jpg	2026-01-07 18:24:49.626279	27.04	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
324	Cointreau 1L	Tequila	44.52	50	\N	/data/product_images/324_Cointreau_1L.jpg	2026-01-07 18:24:49.626279	32.98	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
325	Cointreau 1.75L	Tequila	71.28	50	\N	/data/product_images/325_Cointreau_1.75L.jpg	2026-01-07 18:24:49.626279	52.80	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
326	Espolòn 50ml	Tequila	3.64	50	\N	/data/product_images/326_Espolòn_50ml.jpg	2026-01-07 18:24:49.626279	2.70	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
327	Espolòn 375ml	Tequila	19.58	50	\N	/data/product_images/327_Espolòn_375ml.jpg	2026-01-07 18:24:49.626279	14.50	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
328	Espolòn 750ml	Tequila	35.31	50	\N	/data/product_images/328_Espolòn_750ml.jpg	2026-01-07 18:24:49.626279	26.16	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
329	Espolòn 1L	Tequila	44.65	50	\N	/data/product_images/329_Espolòn_1L.jpg	2026-01-07 18:24:49.626279	33.07	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
330	Espolòn 1.75L	Tequila	67.80	50	\N	/data/product_images/330_Espolòn_1.75L.jpg	2026-01-07 18:24:49.626279	50.22	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
331	Sauza 50ml	Tequila	3.54	50	\N	/data/product_images/331_Sauza_50ml.jpg	2026-01-07 18:24:49.626279	2.62	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
514	Glenlivet 1L	Whiskey	47.50	50	\N	/data/product_images/514_Glenlivet_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
515	Glenlivet 1.75L	Whiskey	76.00	50	\N	/data/product_images/515_Glenlivet_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
634	Ron Zacapa 1L	Rum	40.00	50	\N	/data/product_images/634_Ron_Zacapa_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
635	Ron Zacapa 1.75L	Rum	64.00	50	\N	/data/product_images/635_Ron_Zacapa_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
636	El Dorado 50ml	Rum	3.20	50	\N	/data/product_images/636_El_Dorado_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
637	El Dorado 375ml	Rum	17.60	50	\N	/data/product_images/637_El_Dorado_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
638	El Dorado 750ml	Rum	32.00	50	\N	/data/product_images/638_El_Dorado_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
639	El Dorado 1L	Rum	40.00	50	\N	/data/product_images/639_El_Dorado_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
640	El Dorado 1.75L	Rum	64.00	50	\N	/data/product_images/640_El_Dorado_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
641	Brugal 50ml	Rum	3.20	50	\N	/data/product_images/641_Brugal_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
516	Balvenie 50ml	Whiskey	3.80	50	\N	/data/product_images/516_Balvenie_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
517	Balvenie 375ml	Whiskey	20.90	50	\N	/data/product_images/517_Balvenie_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
518	Balvenie 750ml	Whiskey	38.00	50	\N	/data/product_images/518_Balvenie_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
519	Balvenie 1L	Whiskey	47.50	50	\N	/data/product_images/519_Balvenie_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
520	Balvenie 1.75L	Whiskey	76.00	50	\N	/data/product_images/520_Balvenie_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
521	Lagavulin 50ml	Whiskey	3.80	50	\N	/data/product_images/521_Lagavulin_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
522	Lagavulin 375ml	Whiskey	20.90	50	\N	/data/product_images/522_Lagavulin_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
523	Lagavulin 750ml	Whiskey	38.00	50	\N	/data/product_images/523_Lagavulin_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
524	Lagavulin 1L	Whiskey	47.50	50	\N	/data/product_images/524_Lagavulin_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
525	Lagavulin 1.75L	Whiskey	76.00	50	\N	/data/product_images/525_Lagavulin_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
526	Talisker 50ml	Whiskey	3.80	50	\N	/data/product_images/526_Talisker_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
527	Talisker 375ml	Whiskey	20.90	50	\N	/data/product_images/527_Talisker_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
528	Talisker 750ml	Whiskey	38.00	50	\N	/data/product_images/528_Talisker_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
529	Talisker 1L	Whiskey	47.50	50	\N	/data/product_images/529_Talisker_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
530	Talisker 1.75L	Whiskey	76.00	50	\N	/data/product_images/530_Talisker_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
531	Highland Park 50ml	Whiskey	3.80	50	\N	/data/product_images/531_Highland_Park_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
642	Brugal 375ml	Rum	17.60	50	\N	/data/product_images/642_Brugal_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
643	Brugal 750ml	Rum	32.00	50	\N	/data/product_images/643_Brugal_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
644	Brugal 1L	Rum	40.00	50	\N	/data/product_images/644_Brugal_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
645	Brugal 1.75L	Rum	64.00	50	\N	/data/product_images/645_Brugal_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
350	Gallo Cabernet 375ml	Wine - Red	9.55	50	\N	/data/product_images/350_Gallo_Cabernet_375ml.jpg	2026-01-07 18:24:49.629102	7.07	35.00	0.10	0.00	f	Red wine. Full-bodied with fruit-forward character.
646	Matusalem 50ml	Rum	3.20	50	\N	/data/product_images/646_Matusalem_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
647	Matusalem 375ml	Rum	17.60	50	\N	/data/product_images/647_Matusalem_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
648	Matusalem 750ml	Rum	32.00	50	\N	/data/product_images/648_Matusalem_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
649	Matusalem 1L	Rum	40.00	50	\N	/data/product_images/649_Matusalem_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
64	Premium Mix Snacks - Mixed Nuts	snacks	8.00	75	\N	/data/product_images/64_Premium_Mix_Snacks_-_Mixed_Nut.jpg	2026-01-07 18:21:51.425497	5.93	35.00	0.10	0.00	f	\N
650	Matusalem 1.75L	Rum	64.00	50	\N	/data/product_images/650_Matusalem_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
651	Zacapa 23yr 50ml	Rum	3.20	50	\N	/data/product_images/651_Zacapa_23yr_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
652	Zacapa 23yr 375ml	Rum	17.60	50	\N	/data/product_images/652_Zacapa_23yr_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
653	Zacapa 23yr 750ml	Rum	32.00	50	\N	/data/product_images/653_Zacapa_23yr_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
654	Zacapa 23yr 1L	Rum	40.00	50	\N	/data/product_images/654_Zacapa_23yr_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
655	Zacapa 23yr 1.75L	Rum	64.00	50	\N	/data/product_images/655_Zacapa_23yr_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
656	Havana 7yr 50ml	Rum	3.20	50	\N	/data/product_images/656_Havana_7yr_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
657	Havana 7yr 375ml	Rum	17.60	50	\N	/data/product_images/657_Havana_7yr_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
658	Havana 7yr 750ml	Rum	32.00	50	\N	/data/product_images/658_Havana_7yr_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
659	Havana 7yr 1L	Rum	40.00	50	\N	/data/product_images/659_Havana_7yr_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
660	Havana 7yr 1.75L	Rum	64.00	50	\N	/data/product_images/660_Havana_7yr_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
661	Banks Rum 50ml	Rum	3.20	50	\N	/data/product_images/661_Banks_Rum_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Tropical spirit with caramel and vanilla notes
662	Banks Rum 375ml	Rum	17.60	50	\N	/data/product_images/662_Banks_Rum_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Tropical spirit with caramel and vanilla notes
663	Banks Rum 750ml	Rum	32.00	50	\N	/data/product_images/663_Banks_Rum_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Tropical spirit with caramel and vanilla notes
664	Banks Rum 1L	Rum	40.00	50	\N	/data/product_images/664_Banks_Rum_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Tropical spirit with caramel and vanilla notes
665	Banks Rum 1.75L	Rum	64.00	50	\N	/data/product_images/665_Banks_Rum_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Tropical spirit with caramel and vanilla notes
666	Bundaberg 50ml	Rum	3.20	50	\N	/data/product_images/666_Bundaberg_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
667	Bundaberg 375ml	Rum	17.60	50	\N	/data/product_images/667_Bundaberg_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
668	Bundaberg 750ml	Rum	32.00	50	\N	/data/product_images/668_Bundaberg_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
669	Bundaberg 1L	Rum	40.00	50	\N	/data/product_images/669_Bundaberg_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
66	Grey Goose Vodka - Premium	spirits	80.00	75	\N	/data/product_images/66_Grey_Goose_Vodka_-_Premium.jpg	2026-01-07 18:21:51.425497	59.26	35.00	0.10	0.00	f	Neutral spirit, versatile for mixed drinks
670	Bundaberg 1.75L	Rum	64.00	50	\N	/data/product_images/670_Bundaberg_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
671	Pampero 50ml	Rum	3.20	50	\N	/data/product_images/671_Pampero_50ml.jpg	2026-01-07 18:25:13.617273	2.37	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
672	Pampero 375ml	Rum	17.60	50	\N	/data/product_images/672_Pampero_375ml.jpg	2026-01-07 18:25:13.617273	13.04	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
673	Pampero 750ml	Rum	32.00	50	\N	/data/product_images/673_Pampero_750ml.jpg	2026-01-07 18:25:13.617273	23.70	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
674	Pampero 1L	Rum	40.00	50	\N	/data/product_images/674_Pampero_1L.jpg	2026-01-07 18:25:13.617273	29.63	35.00	0.10	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
675	Pampero 1.75L	Rum	64.00	50	\N	/data/product_images/675_Pampero_1.75L.jpg	2026-01-07 18:25:13.617273	47.41	35.00	0.25	0.00	f	Quality rum. Full-bodied with smooth character. Perfect for cocktails.
676	Plymouth Gin 50ml	Gin	3.60	50	\N	/data/product_images/676_Plymouth_Gin_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Botanical spirit with juniper and spice notes
677	Plymouth Gin 375ml	Gin	19.80	50	\N	/data/product_images/677_Plymouth_Gin_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Botanical spirit with juniper and spice notes
678	Plymouth Gin 750ml	Gin	36.00	50	\N	/data/product_images/678_Plymouth_Gin_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Botanical spirit with juniper and spice notes
400	Chablis 1.75L	Wine - White	33.38	50	\N	/data/product_images/400_Chablis_1.75L.jpg	2026-01-07 18:24:49.631936	24.73	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
404	Saint Clair Sauvignon 375ml	Wine - White	8.68	50	\N	/data/product_images/404_Saint_Clair_Sauvignon_375ml.jpg	2026-01-07 18:24:49.631936	6.43	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
405	Saint Clair Sauvignon 750ml	Wine - White	16.26	50	\N	/data/product_images/405_Saint_Clair_Sauvignon_750ml.jpg	2026-01-07 18:24:49.631936	12.04	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
406	Saint Clair Sauvignon 1.75L	Wine - White	33.52	50	\N	/data/product_images/406_Saint_Clair_Sauvignon_1.75L.jpg	2026-01-07 18:24:49.631936	24.83	35.00	0.25	0.00	f	White wine. Crisp, refreshing with balanced acidity.
407	Sancerre 375ml	Wine - White	8.74	50	\N	/data/product_images/407_Sancerre_375ml.jpg	2026-01-07 18:24:49.631936	6.47	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
408	Sancerre 750ml	Wine - White	15.34	50	\N	/data/product_images/408_Sancerre_750ml.jpg	2026-01-07 18:24:49.631936	11.36	35.00	0.10	0.00	f	White wine. Crisp, refreshing with balanced acidity.
679	Plymouth Gin 1L	Gin	45.00	50	\N	/data/product_images/679_Plymouth_Gin_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Botanical spirit with juniper and spice notes
680	Plymouth Gin 1.75L	Gin	72.00	50	\N	/data/product_images/680_Plymouth_Gin_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Botanical spirit with juniper and spice notes
681	Bols Genever 50ml	Gin	3.60	50	\N	/data/product_images/681_Bols_Genever_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
682	Bols Genever 375ml	Gin	19.80	50	\N	/data/product_images/682_Bols_Genever_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
683	Bols Genever 750ml	Gin	36.00	50	\N	/data/product_images/683_Bols_Genever_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
684	Bols Genever 1L	Gin	45.00	50	\N	/data/product_images/684_Bols_Genever_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
685	Bols Genever 1.75L	Gin	72.00	50	\N	/data/product_images/685_Bols_Genever_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
686	New Amsterdam 50ml	Gin	3.60	50	\N	/data/product_images/686_New_Amsterdam_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
687	New Amsterdam 375ml	Gin	19.80	50	\N	/data/product_images/687_New_Amsterdam_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
688	New Amsterdam 750ml	Gin	36.00	50	\N	/data/product_images/688_New_Amsterdam_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
689	New Amsterdam 1L	Gin	45.00	50	\N	/data/product_images/689_New_Amsterdam_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
68	Macallan 12yr Whiskey - Single Malt	spirits	150.00	75	\N	/data/product_images/68_Macallan_12yr_Whiskey_-_Single.jpg	2026-01-07 18:21:51.425497	111.11	35.00	0.10	0.00	f	Aged spirit with complex oak and grain flavors
690	New Amsterdam 1.75L	Gin	72.00	50	\N	/data/product_images/690_New_Amsterdam_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
691	Beefeater 24 50ml	Gin	3.60	50	\N	/data/product_images/691_Beefeater_24_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
692	Beefeater 24 375ml	Gin	19.80	50	\N	/data/product_images/692_Beefeater_24_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
693	Beefeater 24 750ml	Gin	36.00	50	\N	/data/product_images/693_Beefeater_24_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
705	Tanqueray 10 1.75L	Gin	72.00	50	\N	/data/product_images/705_Tanqueray_10_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
706	Citadelle 50ml	Gin	3.60	50	\N	/data/product_images/706_Citadelle_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
707	Citadelle 375ml	Gin	19.80	50	\N	/data/product_images/707_Citadelle_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
708	Citadelle 750ml	Gin	36.00	50	\N	/data/product_images/708_Citadelle_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
709	Citadelle 1L	Gin	45.00	50	\N	/data/product_images/709_Citadelle_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
70	Dom Perignon Champagne - Dom Perignon	wine	250.00	75	\N	/data/product_images/70_Dom_Perignon_Champagne_-_Dom_P.jpg	2026-01-07 18:21:51.425497	185.19	35.00	0.10	0.00	f	Sparkling wine, celebratory and elegant
710	Citadelle 1.75L	Gin	72.00	50	\N	/data/product_images/710_Citadelle_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
711	Roku 50ml	Gin	3.60	50	\N	/data/product_images/711_Roku_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
712	Roku 375ml	Gin	19.80	50	\N	/data/product_images/712_Roku_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
713	Roku 750ml	Gin	36.00	50	\N	/data/product_images/713_Roku_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
714	Roku 1L	Gin	45.00	50	\N	/data/product_images/714_Roku_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
715	Roku 1.75L	Gin	72.00	50	\N	/data/product_images/715_Roku_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
716	Bombay 50ml	Gin	3.60	50	\N	/data/product_images/716_Bombay_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
717	Bombay 375ml	Gin	19.80	50	\N	/data/product_images/717_Bombay_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
718	Bombay 750ml	Gin	36.00	50	\N	/data/product_images/718_Bombay_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
719	Bombay 1L	Gin	45.00	50	\N	/data/product_images/719_Bombay_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
720	Bombay 1.75L	Gin	72.00	50	\N	/data/product_images/720_Bombay_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
721	Seagram's Extra Dry 50ml	Gin	3.60	50	\N	/data/product_images/721_Seagram's_Extra_Dry_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
722	Seagram's Extra Dry 375ml	Gin	19.80	50	\N	/data/product_images/722_Seagram's_Extra_Dry_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
723	Seagram's Extra Dry 750ml	Gin	36.00	50	\N	/data/product_images/723_Seagram's_Extra_Dry_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
72	Robert Mondavi Wine - Cabernet Sauvignon	wine	45.00	75	\N	/data/product_images/72_Robert_Mondavi_Wine_-_Cabernet.jpg	2026-01-07 18:21:51.425497	33.33	35.00	0.10	0.00	f	Bold red wine with berry and oak flavors
735	Casa Numero Uno 1.75L	Tequila	76.00	50	\N	/data/product_images/735_Casa_Numero_Uno_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
736	Benromach 50ml	Tequila	3.80	50	\N	/data/product_images/736_Benromach_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
737	Benromach 375ml	Tequila	20.90	50	\N	/data/product_images/737_Benromach_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
738	Benromach 750ml	Tequila	38.00	50	\N	/data/product_images/738_Benromach_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
739	Benromach 1L	Tequila	47.50	50	\N	/data/product_images/739_Benromach_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
740	Benromach 1.75L	Tequila	76.00	50	\N	/data/product_images/740_Benromach_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
741	Milagro 50ml	Tequila	3.80	50	\N	/data/product_images/741_Milagro_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
742	Milagro 375ml	Tequila	20.90	50	\N	/data/product_images/742_Milagro_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
743	Milagro 750ml	Tequila	38.00	50	\N	/data/product_images/743_Milagro_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
744	Milagro 1L	Tequila	47.50	50	\N	/data/product_images/744_Milagro_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
745	Milagro 1.75L	Tequila	76.00	50	\N	/data/product_images/745_Milagro_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
746	Fortaleza 50ml	Tequila	3.80	50	\N	/data/product_images/746_Fortaleza_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
747	Fortaleza 375ml	Tequila	20.90	50	\N	/data/product_images/747_Fortaleza_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
748	Fortaleza 750ml	Tequila	38.00	50	\N	/data/product_images/748_Fortaleza_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
749	Fortaleza 1L	Tequila	47.50	50	\N	/data/product_images/749_Fortaleza_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
74	Kendall Jackson Wine - Chardonnay	wine	40.00	75	\N	/data/product_images/74_Kendall_Jackson_Wine_-_Chardon.jpg	2026-01-07 18:21:51.425497	29.63	35.00	0.10	0.00	f	Rich white wine with butter and oak flavors
750	Fortaleza 1.75L	Tequila	76.00	50	\N	/data/product_images/750_Fortaleza_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
751	El Tesoro Paradiso 50ml	Tequila	3.80	50	\N	/data/product_images/751_El_Tesoro_Paradiso_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
752	El Tesoro Paradiso 375ml	Tequila	20.90	50	\N	/data/product_images/752_El_Tesoro_Paradiso_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
753	El Tesoro Paradiso 750ml	Tequila	38.00	50	\N	/data/product_images/753_El_Tesoro_Paradiso_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
754	El Tesoro Paradiso 1L	Tequila	47.50	50	\N	/data/product_images/754_El_Tesoro_Paradiso_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
755	El Tesoro Paradiso 1.75L	Tequila	76.00	50	\N	/data/product_images/755_El_Tesoro_Paradiso_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
756	Centinela 50ml	Tequila	3.80	50	\N	/data/product_images/756_Centinela_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
532	Highland Park 375ml	Whiskey	20.90	50	\N	/data/product_images/532_Highland_Park_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
533	Highland Park 750ml	Whiskey	38.00	50	\N	/data/product_images/533_Highland_Park_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
534	Highland Park 1L	Whiskey	47.50	50	\N	/data/product_images/534_Highland_Park_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
535	Highland Park 1.75L	Whiskey	76.00	50	\N	/data/product_images/535_Highland_Park_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
536	Oban 50ml	Whiskey	3.80	50	\N	/data/product_images/536_Oban_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
537	Oban 375ml	Whiskey	20.90	50	\N	/data/product_images/537_Oban_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
538	Oban 750ml	Whiskey	38.00	50	\N	/data/product_images/538_Oban_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
539	Oban 1L	Whiskey	47.50	50	\N	/data/product_images/539_Oban_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
540	Oban 1.75L	Whiskey	76.00	50	\N	/data/product_images/540_Oban_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
541	Glenfarclas 50ml	Whiskey	3.80	50	\N	/data/product_images/541_Glenfarclas_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
542	Glenfarclas 375ml	Whiskey	20.90	50	\N	/data/product_images/542_Glenfarclas_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
543	Glenfarclas 750ml	Whiskey	38.00	50	\N	/data/product_images/543_Glenfarclas_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
544	Glenfarclas 1L	Whiskey	47.50	50	\N	/data/product_images/544_Glenfarclas_1L.jpg	2026-01-07 18:25:13.607346	35.19	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
545	Glenfarclas 1.75L	Whiskey	76.00	50	\N	/data/product_images/545_Glenfarclas_1.75L.jpg	2026-01-07 18:25:13.607346	56.30	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
546	Macallan Single Malt 50ml	Whiskey	3.80	50	\N	/data/product_images/546_Macallan_Single_Malt_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
547	Macallan Single Malt 375ml	Whiskey	20.90	50	\N	/data/product_images/547_Macallan_Single_Malt_375ml.jpg	2026-01-07 18:25:13.607346	15.48	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
548	Macallan Single Malt 750ml	Whiskey	38.00	50	\N	/data/product_images/548_Macallan_Single_Malt_750ml.jpg	2026-01-07 18:25:13.607346	28.15	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
556	Laphroaig 50ml	Whiskey	3.80	50	\N	/data/product_images/556_Laphroaig_50ml.jpg	2026-01-07 18:25:13.607346	2.81	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
694	Beefeater 24 1L	Gin	45.00	50	\N	/data/product_images/694_Beefeater_24_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	London dry gin with prominent juniper and orange peel.
695	Beefeater 24 1.75L	Gin	72.00	50	\N	/data/product_images/695_Beefeater_24_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	London dry gin with prominent juniper and orange peel.
696	Monkey 47 50ml	Gin	3.60	50	\N	/data/product_images/696_Monkey_47_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
697	Monkey 47 375ml	Gin	19.80	50	\N	/data/product_images/697_Monkey_47_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
698	Monkey 47 750ml	Gin	36.00	50	\N	/data/product_images/698_Monkey_47_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
699	Monkey 47 1L	Gin	45.00	50	\N	/data/product_images/699_Monkey_47_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
700	Monkey 47 1.75L	Gin	72.00	50	\N	/data/product_images/700_Monkey_47_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
701	Tanqueray 10 50ml	Gin	3.60	50	\N	/data/product_images/701_Tanqueray_10_50ml.jpg	2026-01-07 18:25:13.621343	2.67	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
702	Tanqueray 10 375ml	Gin	19.80	50	\N	/data/product_images/702_Tanqueray_10_375ml.jpg	2026-01-07 18:25:13.621343	14.67	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
703	Tanqueray 10 750ml	Gin	36.00	50	\N	/data/product_images/703_Tanqueray_10_750ml.jpg	2026-01-07 18:25:13.621343	26.67	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
704	Tanqueray 10 1L	Gin	45.00	50	\N	/data/product_images/704_Tanqueray_10_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Classic London dry gin. Strong juniper, balanced botanicals.
724	Seagram's Extra Dry 1L	Gin	45.00	50	\N	/data/product_images/724_Seagram's_Extra_Dry_1L.jpg	2026-01-07 18:25:13.621343	33.33	35.00	0.10	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
725	Seagram's Extra Dry 1.75L	Gin	72.00	50	\N	/data/product_images/725_Seagram's_Extra_Dry_1.75L.jpg	2026-01-07 18:25:13.621343	53.33	35.00	0.25	0.00	f	Quality gin with balanced botanicals. Classic for martinis and gin & tonics.
726	Hermanos Serrano 50ml	Tequila	3.80	50	\N	/data/product_images/726_Hermanos_Serrano_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
727	Hermanos Serrano 375ml	Tequila	20.90	50	\N	/data/product_images/727_Hermanos_Serrano_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
728	Hermanos Serrano 750ml	Tequila	38.00	50	\N	/data/product_images/728_Hermanos_Serrano_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
729	Hermanos Serrano 1L	Tequila	47.50	50	\N	/data/product_images/729_Hermanos_Serrano_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
730	Hermanos Serrano 1.75L	Tequila	76.00	50	\N	/data/product_images/730_Hermanos_Serrano_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
731	Casa Numero Uno 50ml	Tequila	3.80	50	\N	/data/product_images/731_Casa_Numero_Uno_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
732	Casa Numero Uno 375ml	Tequila	20.90	50	\N	/data/product_images/732_Casa_Numero_Uno_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
733	Casa Numero Uno 750ml	Tequila	38.00	50	\N	/data/product_images/733_Casa_Numero_Uno_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
734	Casa Numero Uno 1L	Tequila	47.50	50	\N	/data/product_images/734_Casa_Numero_Uno_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
1027	Apothic Red 1L	Wine - Red	24.99	\N	\N	\N	2026-01-08 14:36:42.348195	17.49	35.00	0.10	0.00	f	Red blend with berry and spice notes
1028	Apothic Decadent 750ml	Wine - Red	21.99	\N	\N	\N	2026-01-08 14:36:42.348195	15.39	35.00	0.10	0.00	f	Premium red blend with caramel and vanilla
1029	Apothic Decadent 1L	Wine - Red	28.99	\N	\N	\N	2026-01-08 14:36:42.348195	20.29	35.00	0.10	0.00	f	Premium red blend with caramel and vanilla
1030	Apothic Inferno 750ml	Wine - Red	19.99	\N	\N	\N	2026-01-08 14:36:42.348195	13.99	35.00	0.10	0.00	f	Spiced red blend with dark fruit
1031	Apothic Inferno 1L	Wine - Red	25.99	\N	\N	\N	2026-01-08 14:36:42.348195	18.19	35.00	0.10	0.00	f	Spiced red blend with dark fruit
1032	Barefoot Cabernet 1L	Wine - Red	24.99	\N	\N	\N	2026-01-08 14:36:42.348195	17.49	35.00	0.10	0.00	f	California Cabernet, smooth and fruit-forward
1033	Hennessy VS 50ml	Brandy	4.99	\N	\N	\N	2026-01-08 14:36:42.348195	3.49	35.00	0.10	0.00	f	French cognac, smooth oak and vanilla
1034	Hennessy VS 375ml	Brandy	28.99	\N	\N	\N	2026-01-08 14:36:42.348195	20.29	35.00	0.10	0.00	f	French cognac, smooth oak and vanilla
1035	Hennessy VS 750ml	Brandy	54.99	\N	\N	\N	2026-01-08 14:36:42.348195	38.49	35.00	0.10	0.00	f	French cognac, smooth oak and vanilla
1036	Hennessy VSOP 750ml	Brandy	72.99	\N	\N	\N	2026-01-08 14:36:42.348195	51.09	35.00	0.10	0.00	f	Premium French cognac, aged complexity
1037	Parallel 49 Brewing 355ml	Craft Beer	2.80	\N	\N	\N	2026-01-08 14:36:42.348195	1.96	35.00	0.10	0.00	f	Vancouver craft brewery, bold flavors
1038	Parallel 49 Brewing 473ml	Craft Beer	3.99	\N	\N	\N	2026-01-08 14:36:42.348195	2.79	35.00	0.10	0.00	f	Vancouver craft brewery, bold flavors
1039	Shed & Breakfast IPA 355ml	Craft Beer	2.75	\N	\N	\N	2026-01-08 14:36:42.348195	1.93	35.00	0.10	0.00	f	Alberta IPA, citrus and pine hops
1040	San Pellegrino Sparkling Water 500ml	Water	3.50	\N	\N	\N	2026-01-08 14:36:42.348195	2.45	35.00	0.10	0.00	f	Italian sparkling mineral water
1042	Barefoot Bubbly 1L	Champagne	107.72	0	\N	\N	2026-01-08 14:42:13.491013	75.40	35.00	0.10	0.00	f	Barefoot Bubbly wine - 1L bottle
1043	Barefoot Bubbly Brut 1L	Champagne	20.35	0	\N	\N	2026-01-08 14:42:13.491013	14.25	35.00	0.10	0.00	f	Barefoot Bubbly Brut wine - 1L bottle
1020	Ace 355ml	Ciders	3.75	50	\N	/data/product_images/1020_Ace_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1021	Ace 473ml	Ciders	4.88	50	\N	/data/product_images/1021_Ace_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1022	Ace 24-pack	Ciders	180.00	50	\N	/data/product_images/1022_Ace_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
1023	Hornsby's 355ml	Ciders	3.75	50	\N	/data/product_images/1023_Hornsby's_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1024	Hornsby's 473ml	Ciders	4.88	50	\N	/data/product_images/1024_Hornsby's_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
1025	Hornsby's 24-pack	Ciders	180.00	50	\N	/data/product_images/1025_Hornsby's_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
757	Centinela 375ml	Tequila	20.90	50	\N	/data/product_images/757_Centinela_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
758	Centinela 750ml	Tequila	38.00	50	\N	/data/product_images/758_Centinela_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
759	Centinela 1L	Tequila	47.50	50	\N	/data/product_images/759_Centinela_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
760	Centinela 1.75L	Tequila	76.00	50	\N	/data/product_images/760_Centinela_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
761	Sauza Tres Mujeres 50ml	Tequila	3.80	50	\N	/data/product_images/761_Sauza_Tres_Mujeres_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
762	Sauza Tres Mujeres 375ml	Tequila	20.90	50	\N	/data/product_images/762_Sauza_Tres_Mujeres_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
763	Sauza Tres Mujeres 750ml	Tequila	38.00	50	\N	/data/product_images/763_Sauza_Tres_Mujeres_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
764	Sauza Tres Mujeres 1L	Tequila	47.50	50	\N	/data/product_images/764_Sauza_Tres_Mujeres_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
765	Sauza Tres Mujeres 1.75L	Tequila	76.00	50	\N	/data/product_images/765_Sauza_Tres_Mujeres_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
766	Siesta 50ml	Tequila	3.80	50	\N	/data/product_images/766_Siesta_50ml.jpg	2026-01-07 18:25:13.625456	2.81	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
767	Siesta 375ml	Tequila	20.90	50	\N	/data/product_images/767_Siesta_375ml.jpg	2026-01-07 18:25:13.625456	15.48	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
768	Siesta 750ml	Tequila	38.00	50	\N	/data/product_images/768_Siesta_750ml.jpg	2026-01-07 18:25:13.625456	28.15	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
769	Siesta 1L	Tequila	47.50	50	\N	/data/product_images/769_Siesta_1L.jpg	2026-01-07 18:25:13.625456	35.19	35.00	0.10	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
76	Jim Beam 50ml	Whiskey	3.32	50	\N	/data/product_images/76_Jim_Beam_50ml.jpg	2026-01-07 18:24:49.609209	2.46	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
770	Siesta 1.75L	Tequila	76.00	50	\N	/data/product_images/770_Siesta_1.75L.jpg	2026-01-07 18:25:13.625456	56.30	35.00	0.25	0.00	f	Premium tequila. Smooth, versatile for margaritas and cocktails.
797	Amaretto 375ml	Liqueurs	19.25	50	\N	/data/product_images/797_Amaretto_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
798	Amaretto 750ml	Liqueurs	35.00	50	\N	/data/product_images/798_Amaretto_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
799	Amaretto 1L	Liqueurs	43.75	50	\N	/data/product_images/799_Amaretto_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
79	Jim Beam 1L	Whiskey	41.65	50	\N	/data/product_images/79_Jim_Beam_1L.jpg	2026-01-07 18:24:49.609209	30.85	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
800	Amaretto 1.75L	Liqueurs	70.00	50	\N	/data/product_images/800_Amaretto_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
801	Frangelico 50ml	Liqueurs	3.50	50	\N	/data/product_images/801_Frangelico_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
802	Frangelico 375ml	Liqueurs	19.25	50	\N	/data/product_images/802_Frangelico_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
803	Frangelico 750ml	Liqueurs	35.00	50	\N	/data/product_images/803_Frangelico_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
804	Frangelico 1L	Liqueurs	43.75	50	\N	/data/product_images/804_Frangelico_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
805	Frangelico 1.75L	Liqueurs	70.00	50	\N	/data/product_images/805_Frangelico_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
806	Benedictine 50ml	Liqueurs	3.50	50	\N	/data/product_images/806_Benedictine_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
807	Benedictine 375ml	Liqueurs	19.25	50	\N	/data/product_images/807_Benedictine_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
808	Benedictine 750ml	Liqueurs	35.00	50	\N	/data/product_images/808_Benedictine_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
809	Benedictine 1L	Liqueurs	43.75	50	\N	/data/product_images/809_Benedictine_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
80	Jim Beam 1.75L	Whiskey	62.67	50	\N	/data/product_images/80_Jim_Beam_1.75L.jpg	2026-01-07 18:24:49.609209	46.42	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
810	Benedictine 1.75L	Liqueurs	70.00	50	\N	/data/product_images/810_Benedictine_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
811	Chartreuse 50ml	Liqueurs	3.50	50	\N	/data/product_images/811_Chartreuse_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
812	Chartreuse 375ml	Liqueurs	19.25	50	\N	/data/product_images/812_Chartreuse_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
813	Chartreuse 750ml	Liqueurs	35.00	50	\N	/data/product_images/813_Chartreuse_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
814	Chartreuse 1L	Liqueurs	43.75	50	\N	/data/product_images/814_Chartreuse_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
815	Chartreuse 1.75L	Liqueurs	70.00	50	\N	/data/product_images/815_Chartreuse_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
816	Drambuie 50ml	Liqueurs	3.50	50	\N	/data/product_images/816_Drambuie_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
817	Drambuie 375ml	Liqueurs	19.25	50	\N	/data/product_images/817_Drambuie_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
818	Drambuie 750ml	Liqueurs	35.00	50	\N	/data/product_images/818_Drambuie_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
819	Drambuie 1L	Liqueurs	43.75	50	\N	/data/product_images/819_Drambuie_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
81	Jack Daniels 50ml	Whiskey	3.17	50	\N	/data/product_images/81_Jack_Daniels_50ml.jpg	2026-01-07 18:24:49.609209	2.35	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
820	Drambuie 1.75L	Liqueurs	70.00	50	\N	/data/product_images/820_Drambuie_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
821	Chambord 50ml	Liqueurs	3.50	50	\N	/data/product_images/821_Chambord_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
822	Chambord 375ml	Liqueurs	19.25	50	\N	/data/product_images/822_Chambord_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
823	Chambord 750ml	Liqueurs	35.00	50	\N	/data/product_images/823_Chambord_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
824	Chambord 1L	Liqueurs	43.75	50	\N	/data/product_images/824_Chambord_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
825	Chambord 1.75L	Liqueurs	70.00	50	\N	/data/product_images/825_Chambord_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
826	Midori 50ml	Liqueurs	3.50	50	\N	/data/product_images/826_Midori_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
827	Midori 375ml	Liqueurs	19.25	50	\N	/data/product_images/827_Midori_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
828	Midori 750ml	Liqueurs	35.00	50	\N	/data/product_images/828_Midori_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
829	Midori 1L	Liqueurs	43.75	50	\N	/data/product_images/829_Midori_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
82	Jack Daniels 375ml	Whiskey	17.26	50	\N	/data/product_images/82_Jack_Daniels_375ml.jpg	2026-01-07 18:24:49.609209	12.79	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
830	Midori 1.75L	Liqueurs	70.00	50	\N	/data/product_images/830_Midori_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
831	Limoncello 50ml	Liqueurs	3.50	50	\N	/data/product_images/831_Limoncello_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
832	Limoncello 375ml	Liqueurs	19.25	50	\N	/data/product_images/832_Limoncello_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
833	Limoncello 750ml	Liqueurs	35.00	50	\N	/data/product_images/833_Limoncello_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
834	Limoncello 1L	Liqueurs	43.75	50	\N	/data/product_images/834_Limoncello_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
835	Limoncello 1.75L	Liqueurs	70.00	50	\N	/data/product_images/835_Limoncello_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
836	Disaronno 50ml	Liqueurs	3.50	50	\N	/data/product_images/836_Disaronno_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
837	Disaronno 375ml	Liqueurs	19.25	50	\N	/data/product_images/837_Disaronno_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
838	Disaronno 750ml	Liqueurs	35.00	50	\N	/data/product_images/838_Disaronno_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
839	Disaronno 1L	Liqueurs	43.75	50	\N	/data/product_images/839_Disaronno_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
83	Jack Daniels 750ml	Whiskey	30.66	50	\N	/data/product_images/83_Jack_Daniels_750ml.jpg	2026-01-07 18:24:49.609209	22.71	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
840	Disaronno 1.75L	Liqueurs	70.00	50	\N	/data/product_images/840_Disaronno_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
846	Ouzo 50ml	Liqueurs	3.50	50	\N	/data/product_images/846_Ouzo_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
847	Ouzo 375ml	Liqueurs	19.25	50	\N	/data/product_images/847_Ouzo_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
848	Ouzo 750ml	Liqueurs	35.00	50	\N	/data/product_images/848_Ouzo_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
84	Jack Daniels 1L	Whiskey	41.87	50	\N	/data/product_images/84_Jack_Daniels_1L.jpg	2026-01-07 18:24:49.609209	31.01	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
850	Ouzo 1.75L	Liqueurs	70.00	50	\N	/data/product_images/850_Ouzo_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
851	Campari 50ml	Liqueurs	3.50	50	\N	/data/product_images/851_Campari_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
852	Campari 375ml	Liqueurs	19.25	50	\N	/data/product_images/852_Campari_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
853	Campari 750ml	Liqueurs	35.00	50	\N	/data/product_images/853_Campari_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
854	Campari 1L	Liqueurs	43.75	50	\N	/data/product_images/854_Campari_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
855	Campari 1.75L	Liqueurs	70.00	50	\N	/data/product_images/855_Campari_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
856	Pernod 50ml	Liqueurs	3.50	50	\N	/data/product_images/856_Pernod_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
857	Pernod 375ml	Liqueurs	19.25	50	\N	/data/product_images/857_Pernod_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
858	Pernod 750ml	Liqueurs	35.00	50	\N	/data/product_images/858_Pernod_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
859	Pernod 1L	Liqueurs	43.75	50	\N	/data/product_images/859_Pernod_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
85	Jack Daniels 1.75L	Whiskey	64.41	50	\N	/data/product_images/85_Jack_Daniels_1.75L.jpg	2026-01-07 18:24:49.609209	47.71	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
860	Pernod 1.75L	Liqueurs	70.00	50	\N	/data/product_images/860_Pernod_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
861	Absinthe 50ml	Liqueurs	3.50	50	\N	/data/product_images/861_Absinthe_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
862	Absinthe 375ml	Liqueurs	19.25	50	\N	/data/product_images/862_Absinthe_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
863	Absinthe 750ml	Liqueurs	35.00	50	\N	/data/product_images/863_Absinthe_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
864	Absinthe 1L	Liqueurs	43.75	50	\N	/data/product_images/864_Absinthe_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
865	Absinthe 1.75L	Liqueurs	70.00	50	\N	/data/product_images/865_Absinthe_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
866	Sambuca 50ml	Liqueurs	3.50	50	\N	/data/product_images/866_Sambuca_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
867	Sambuca 375ml	Liqueurs	19.25	50	\N	/data/product_images/867_Sambuca_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
868	Sambuca 750ml	Liqueurs	35.00	50	\N	/data/product_images/868_Sambuca_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
869	Sambuca 1L	Liqueurs	43.75	50	\N	/data/product_images/869_Sambuca_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
86	Crown Royal 50ml	Whiskey	3.30	50	\N	/data/product_images/86_Crown_Royal_50ml.jpg	2026-01-07 18:24:49.609209	2.44	35.00	0.10	0.00	f	Canadian blended whiskey. Smooth, balanced, perfect for any occasion.
870	Sambuca 1.75L	Liqueurs	70.00	50	\N	/data/product_images/870_Sambuca_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
871	Coffee Liqueur 50ml	Liqueurs	3.50	50	\N	/data/product_images/871_Coffee_Liqueur_50ml.jpg	2026-01-07 18:25:13.629453	2.59	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
872	Coffee Liqueur 375ml	Liqueurs	19.25	50	\N	/data/product_images/872_Coffee_Liqueur_375ml.jpg	2026-01-07 18:25:13.629453	14.26	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
873	Coffee Liqueur 750ml	Liqueurs	35.00	50	\N	/data/product_images/873_Coffee_Liqueur_750ml.jpg	2026-01-07 18:25:13.629453	25.93	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
874	Coffee Liqueur 1L	Liqueurs	43.75	50	\N	/data/product_images/874_Coffee_Liqueur_1L.jpg	2026-01-07 18:25:13.629453	32.41	35.00	0.10	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
875	Coffee Liqueur 1.75L	Liqueurs	70.00	50	\N	/data/product_images/875_Coffee_Liqueur_1.75L.jpg	2026-01-07 18:25:13.629453	51.85	35.00	0.25	0.00	f	Premium liqueur. Smooth, versatile for cocktails and shots.
876	Cognac VS 50ml	Brandy	4.50	50	\N	/data/product_images/876_Cognac_VS_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
877	Cognac VS 375ml	Brandy	24.75	50	\N	/data/product_images/877_Cognac_VS_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
878	Cognac VS 750ml	Brandy	45.00	50	\N	/data/product_images/878_Cognac_VS_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
879	Cognac VS 1L	Brandy	56.25	50	\N	/data/product_images/879_Cognac_VS_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
87	Crown Royal 375ml	Whiskey	17.59	50	\N	/data/product_images/87_Crown_Royal_375ml.jpg	2026-01-07 18:24:49.609209	13.03	35.00	0.10	0.00	f	Canadian blended whiskey. Smooth, balanced, perfect for any occasion.
880	Cognac VS 1.75L	Brandy	90.00	50	\N	/data/product_images/880_Cognac_VS_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
881	Cognac VSOP 50ml	Brandy	4.50	50	\N	/data/product_images/881_Cognac_VSOP_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
882	Cognac VSOP 375ml	Brandy	24.75	50	\N	/data/product_images/882_Cognac_VSOP_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
883	Cognac VSOP 750ml	Brandy	45.00	50	\N	/data/product_images/883_Cognac_VSOP_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
884	Cognac VSOP 1L	Brandy	56.25	50	\N	/data/product_images/884_Cognac_VSOP_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
885	Cognac VSOP 1.75L	Brandy	90.00	50	\N	/data/product_images/885_Cognac_VSOP_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
886	Hennessy 50ml	Brandy	4.50	50	\N	/data/product_images/886_Hennessy_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Premium Cognac. Rich, complex, elegant.
887	Hennessy 375ml	Brandy	24.75	50	\N	/data/product_images/887_Hennessy_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Premium Cognac. Rich, complex, elegant.
888	Hennessy 750ml	Brandy	45.00	50	\N	/data/product_images/888_Hennessy_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Premium Cognac. Rich, complex, elegant.
889	Hennessy 1L	Brandy	56.25	50	\N	/data/product_images/889_Hennessy_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Premium Cognac. Rich, complex, elegant.
88	Crown Royal 750ml	Whiskey	33.57	50	\N	/data/product_images/88_Crown_Royal_750ml.jpg	2026-01-07 18:24:49.609209	24.87	35.00	0.10	0.00	f	Canadian blended whiskey. Smooth, balanced, perfect for any occasion.
890	Hennessy 1.75L	Brandy	90.00	50	\N	/data/product_images/890_Hennessy_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Premium Cognac. Rich, complex, elegant.
891	Remy Martin 50ml	Brandy	4.50	50	\N	/data/product_images/891_Remy_Martin_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Smooth Cognac from Champagne region. Refined, fruity notes.
892	Remy Martin 375ml	Brandy	24.75	50	\N	/data/product_images/892_Remy_Martin_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Smooth Cognac from Champagne region. Refined, fruity notes.
893	Remy Martin 750ml	Brandy	45.00	50	\N	/data/product_images/893_Remy_Martin_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Smooth Cognac from Champagne region. Refined, fruity notes.
894	Remy Martin 1L	Brandy	56.25	50	\N	/data/product_images/894_Remy_Martin_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Smooth Cognac from Champagne region. Refined, fruity notes.
895	Remy Martin 1.75L	Brandy	90.00	50	\N	/data/product_images/895_Remy_Martin_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Smooth Cognac from Champagne region. Refined, fruity notes.
896	Courvoisier 50ml	Brandy	4.50	50	\N	/data/product_images/896_Courvoisier_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
897	Courvoisier 375ml	Brandy	24.75	50	\N	/data/product_images/897_Courvoisier_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
898	Courvoisier 750ml	Brandy	45.00	50	\N	/data/product_images/898_Courvoisier_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
899	Courvoisier 1L	Brandy	56.25	50	\N	/data/product_images/899_Courvoisier_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
89	Crown Royal 1L	Whiskey	38.45	50	\N	/data/product_images/89_Crown_Royal_1L.jpg	2026-01-07 18:24:49.609209	28.48	35.00	0.10	0.00	f	Canadian blended whiskey. Smooth, balanced, perfect for any occasion.
900	Courvoisier 1.75L	Brandy	90.00	50	\N	/data/product_images/900_Courvoisier_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
901	Martell 50ml	Brandy	4.50	50	\N	/data/product_images/901_Martell_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
902	Martell 375ml	Brandy	24.75	50	\N	/data/product_images/902_Martell_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
903	Martell 750ml	Brandy	45.00	50	\N	/data/product_images/903_Martell_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
904	Martell 1L	Brandy	56.25	50	\N	/data/product_images/904_Martell_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
905	Martell 1.75L	Brandy	90.00	50	\N	/data/product_images/905_Martell_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
906	Pisco 50ml	Brandy	4.50	50	\N	/data/product_images/906_Pisco_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
907	Pisco 375ml	Brandy	24.75	50	\N	/data/product_images/907_Pisco_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
908	Pisco 750ml	Brandy	45.00	50	\N	/data/product_images/908_Pisco_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
909	Pisco 1L	Brandy	56.25	50	\N	/data/product_images/909_Pisco_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
90	Crown Royal 1.75L	Whiskey	64.70	50	\N	/data/product_images/90_Crown_Royal_1.75L.jpg	2026-01-07 18:24:49.609209	47.93	35.00	0.25	0.00	f	Canadian blended whiskey. Smooth, balanced, perfect for any occasion.
910	Pisco 1.75L	Brandy	90.00	50	\N	/data/product_images/910_Pisco_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
911	Applejack 50ml	Brandy	4.50	50	\N	/data/product_images/911_Applejack_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
912	Applejack 375ml	Brandy	24.75	50	\N	/data/product_images/912_Applejack_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
913	Applejack 750ml	Brandy	45.00	50	\N	/data/product_images/913_Applejack_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
914	Applejack 1L	Brandy	56.25	50	\N	/data/product_images/914_Applejack_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
915	Applejack 1.75L	Brandy	90.00	50	\N	/data/product_images/915_Applejack_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
916	Calvados 50ml	Brandy	4.50	50	\N	/data/product_images/916_Calvados_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
917	Calvados 375ml	Brandy	24.75	50	\N	/data/product_images/917_Calvados_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
918	Calvados 750ml	Brandy	45.00	50	\N	/data/product_images/918_Calvados_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
919	Calvados 1L	Brandy	56.25	50	\N	/data/product_images/919_Calvados_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
91	Canadian Club 50ml	Whiskey	3.22	50	\N	/data/product_images/91_Canadian_Club_50ml.jpg	2026-01-07 18:24:49.609209	2.39	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
920	Calvados 1.75L	Brandy	90.00	50	\N	/data/product_images/920_Calvados_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
921	Grappa 50ml	Brandy	4.50	50	\N	/data/product_images/921_Grappa_50ml.jpg	2026-01-07 18:25:13.636023	3.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
922	Grappa 375ml	Brandy	24.75	50	\N	/data/product_images/922_Grappa_375ml.jpg	2026-01-07 18:25:13.636023	18.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
923	Grappa 750ml	Brandy	45.00	50	\N	/data/product_images/923_Grappa_750ml.jpg	2026-01-07 18:25:13.636023	33.33	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
924	Grappa 1L	Brandy	56.25	50	\N	/data/product_images/924_Grappa_1L.jpg	2026-01-07 18:25:13.636023	41.67	35.00	0.10	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
925	Grappa 1.75L	Brandy	90.00	50	\N	/data/product_images/925_Grappa_1.75L.jpg	2026-01-07 18:25:13.636023	66.67	35.00	0.25	0.00	f	Aged brandy. Rich, complex with oak and fruit character.
926	Seedlip Grove 42 500ml	Non-Alcoholic Spirits	28.00	50	\N	/data/product_images/926_Seedlip_Grove_42_500ml.jpg	2026-01-07 18:25:13.639049	20.74	35.00	0.10	0.00	f	\N
927	Seedlip Grove 42 700ml	Non-Alcoholic Spirits	38.00	50	\N	/data/product_images/927_Seedlip_Grove_42_700ml.jpg	2026-01-07 18:25:13.639049	28.15	35.00	0.10	0.00	f	\N
928	Seedlip Spice 94 500ml	Non-Alcoholic Spirits	28.00	50	\N	/data/product_images/928_Seedlip_Spice_94_500ml.jpg	2026-01-07 18:25:13.639049	20.74	35.00	0.10	0.00	f	\N
929	Seedlip Spice 94 700ml	Non-Alcoholic Spirits	38.00	50	\N	/data/product_images/929_Seedlip_Spice_94_700ml.jpg	2026-01-07 18:25:13.639049	28.15	35.00	0.10	0.00	f	\N
92	Canadian Club 375ml	Whiskey	17.50	50	\N	/data/product_images/92_Canadian_Club_375ml.jpg	2026-01-07 18:24:49.609209	12.96	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
930	Lyre's Dry London Spirit 500ml	Non-Alcoholic Spirits	28.00	50	\N	/data/product_images/930_Lyre's_Dry_London_Spirit_500ml.jpg	2026-01-07 18:25:13.639049	20.74	35.00	0.10	0.00	f	\N
931	Lyre's Dry London Spirit 700ml	Non-Alcoholic Spirits	38.00	50	\N	/data/product_images/931_Lyre's_Dry_London_Spirit_700ml.jpg	2026-01-07 18:25:13.639049	28.15	35.00	0.10	0.00	f	\N
932	Tansie 500ml	Non-Alcoholic Spirits	28.00	50	\N	/data/product_images/932_Tansie_500ml.jpg	2026-01-07 18:25:13.639049	20.74	35.00	0.10	0.00	f	\N
933	Tansie 700ml	Non-Alcoholic Spirits	38.00	50	\N	/data/product_images/933_Tansie_700ml.jpg	2026-01-07 18:25:13.639049	28.15	35.00	0.10	0.00	f	\N
934	Three Spirit Ethica 500ml	Non-Alcoholic Spirits	28.00	50	\N	/data/product_images/934_Three_Spirit_Ethica_500ml.jpg	2026-01-07 18:25:13.639049	20.74	35.00	0.10	0.00	f	\N
935	Three Spirit Ethica 700ml	Non-Alcoholic Spirits	38.00	50	\N	/data/product_images/935_Three_Spirit_Ethica_700ml.jpg	2026-01-07 18:25:13.639049	28.15	35.00	0.10	0.00	f	\N
936	White Claw Mango 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/936_White_Claw_Mango_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
937	White Claw Mango 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/937_White_Claw_Mango_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
938	White Claw Mango 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/938_White_Claw_Mango_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
939	White Claw Lime 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/939_White_Claw_Lime_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
93	Canadian Club 750ml	Whiskey	31.33	50	\N	/data/product_images/93_Canadian_Club_750ml.jpg	2026-01-07 18:24:49.609209	23.21	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
940	White Claw Lime 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/940_White_Claw_Lime_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
941	White Claw Lime 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/941_White_Claw_Lime_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
942	Truly Variety Pack 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/942_Truly_Variety_Pack_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
943	Truly Variety Pack 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/943_Truly_Variety_Pack_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
944	Truly Variety Pack 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/944_Truly_Variety_Pack_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
945	Bud Light Seltzer 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/945_Bud_Light_Seltzer_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Light American lager, smooth and refreshing
946	Bud Light Seltzer 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/946_Bud_Light_Seltzer_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Light American lager, smooth and refreshing
947	Bud Light Seltzer 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/947_Bud_Light_Seltzer_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Light American lager, smooth and refreshing
948	Corona Hard Seltzer 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/948_Corona_Hard_Seltzer_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Light, crisp Mexican lager with citrus notes
949	Corona Hard Seltzer 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/949_Corona_Hard_Seltzer_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Light, crisp Mexican lager with citrus notes
94	Canadian Club 1L	Whiskey	41.51	50	\N	/data/product_images/94_Canadian_Club_1L.jpg	2026-01-07 18:24:49.609209	30.75	35.00	0.10	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
950	Corona Hard Seltzer 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/950_Corona_Hard_Seltzer_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Light, crisp Mexican lager with citrus notes
951	Twisted Tea 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/951_Twisted_Tea_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Refreshing malt-based beverage with natural tea flavors
952	Twisted Tea 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/952_Twisted_Tea_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Refreshing malt-based beverage with natural tea flavors
953	Twisted Tea 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/953_Twisted_Tea_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Refreshing malt-based beverage with natural tea flavors
954	Smirnoff Ice 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/954_Smirnoff_Ice_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
955	Smirnoff Ice 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/955_Smirnoff_Ice_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
956	Smirnoff Ice 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/956_Smirnoff_Ice_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
957	Mike's Hard Lemonade 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/957_Mike's_Hard_Lemonade_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
958	Mike's Hard Lemonade 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/958_Mike's_Hard_Lemonade_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
959	Mike's Hard Lemonade 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/959_Mike's_Hard_Lemonade_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
95	Canadian Club 1.75L	Whiskey	60.98	50	\N	/data/product_images/95_Canadian_Club_1.75L.jpg	2026-01-07 18:24:49.609209	45.17	35.00	0.25	0.00	f	Smooth whiskey. Well-rounded spirit with balanced flavor profile.
960	Burnett's Seltzer 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/960_Burnett's_Seltzer_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
961	Burnett's Seltzer 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/961_Burnett's_Seltzer_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
962	Burnett's Seltzer 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/962_Burnett's_Seltzer_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
963	Henry's Hard Soda 355ml	Hard Seltzers	6.00	50	\N	/data/product_images/963_Henry's_Hard_Soda_355ml.jpg	2026-01-07 18:25:13.639984	4.44	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
964	Henry's Hard Soda 473ml	Hard Seltzers	7.80	50	\N	/data/product_images/964_Henry's_Hard_Soda_473ml.jpg	2026-01-07 18:25:13.639984	5.78	35.00	0.10	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
965	Henry's Hard Soda 24-pack	Hard Seltzers	288.00	50	\N	/data/product_images/965_Henry's_Hard_Soda_24-pack.jpg	2026-01-07 18:25:13.639984	213.33	35.00	2.40	0.00	f	Hard seltzer. Light, refreshing with natural flavors.
966	Moose Jaw Brewing 473ml	Craft Beer	5.53	50	\N	/data/product_images/966_Moose_Jaw_Brewing_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
967	Moose Jaw Brewing 24-pack	Craft Beer	204.00	50	\N	/data/product_images/967_Moose_Jaw_Brewing_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
968	Moose Jaw Brewing 6-pack	Craft Beer	51.00	50	\N	/data/product_images/968_Moose_Jaw_Brewing_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
969	Big Rock Brewery 473ml	Craft Beer	5.53	50	\N	/data/product_images/969_Big_Rock_Brewery_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
96	Jameson 50ml	Whiskey	3.07	50	\N	/data/product_images/96_Jameson_50ml.jpg	2026-01-07 18:24:49.609209	2.27	35.00	0.10	0.00	f	Irish whiskey with triple distillation. Smooth, sweet, triple pot still character.
970	Big Rock Brewery 24-pack	Craft Beer	204.00	50	\N	/data/product_images/970_Big_Rock_Brewery_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
971	Big Rock Brewery 6-pack	Craft Beer	51.00	50	\N	/data/product_images/971_Big_Rock_Brewery_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
972	Noodly Appendage Ale 473ml	Craft Beer	5.53	50	\N	/data/product_images/972_Noodly_Appendage_Ale_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
973	Noodly Appendage Ale 24-pack	Craft Beer	204.00	50	\N	/data/product_images/973_Noodly_Appendage_Ale_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
974	Noodly Appendage Ale 6-pack	Craft Beer	51.00	50	\N	/data/product_images/974_Noodly_Appendage_Ale_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
975	Trolley 5 473ml	Craft Beer	5.53	50	\N	/data/product_images/975_Trolley_5_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
976	Trolley 5 24-pack	Craft Beer	204.00	50	\N	/data/product_images/976_Trolley_5_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
977	Trolley 5 6-pack	Craft Beer	51.00	50	\N	/data/product_images/977_Trolley_5_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
978	Shed & Breakfast IPA 473ml	Craft Beer	5.53	50	\N	/data/product_images/978_Shed_&_Breakfast_IPA_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
979	Shed & Breakfast IPA 24-pack	Craft Beer	204.00	50	\N	/data/product_images/979_Shed_&_Breakfast_IPA_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
97	Jameson 375ml	Whiskey	16.91	50	\N	/data/product_images/97_Jameson_375ml.jpg	2026-01-07 18:24:49.609209	12.53	35.00	0.10	0.00	f	Irish whiskey with triple distillation. Smooth, sweet, triple pot still character.
980	Shed & Breakfast IPA 6-pack	Craft Beer	51.00	50	\N	/data/product_images/980_Shed_&_Breakfast_IPA_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
981	Strathcona Brewing 473ml	Craft Beer	5.53	50	\N	/data/product_images/981_Strathcona_Brewing_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
982	Strathcona Brewing 24-pack	Craft Beer	204.00	50	\N	/data/product_images/982_Strathcona_Brewing_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
983	Strathcona Brewing 6-pack	Craft Beer	51.00	50	\N	/data/product_images/983_Strathcona_Brewing_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
984	Tool Shed Brewing 473ml	Craft Beer	5.53	50	\N	/data/product_images/984_Tool_Shed_Brewing_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
985	Tool Shed Brewing 24-pack	Craft Beer	204.00	50	\N	/data/product_images/985_Tool_Shed_Brewing_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
986	Tool Shed Brewing 6-pack	Craft Beer	51.00	50	\N	/data/product_images/986_Tool_Shed_Brewing_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
987	Folding Mountain Brewing 473ml	Craft Beer	5.53	50	\N	/data/product_images/987_Folding_Mountain_Brewing_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
988	Folding Mountain Brewing 24-pack	Craft Beer	204.00	50	\N	/data/product_images/988_Folding_Mountain_Brewing_24-pa.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
989	Folding Mountain Brewing 6-pack	Craft Beer	51.00	50	\N	/data/product_images/989_Folding_Mountain_Brewing_6-pac.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
98	Jameson 750ml	Whiskey	31.71	50	\N	/data/product_images/98_Jameson_750ml.jpg	2026-01-07 18:24:49.609209	23.49	35.00	0.10	0.00	f	Irish whiskey with triple distillation. Smooth, sweet, triple pot still character.
990	Parallel 49 473ml	Craft Beer	5.53	50	\N	/data/product_images/990_Parallel_49_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
991	Parallel 49 24-pack	Craft Beer	204.00	50	\N	/data/product_images/991_Parallel_49_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
992	Parallel 49 6-pack	Craft Beer	51.00	50	\N	/data/product_images/992_Parallel_49_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
993	Dead Frog Brewing 473ml	Craft Beer	5.53	50	\N	/data/product_images/993_Dead_Frog_Brewing_473ml.jpg	2026-01-07 18:25:13.642262	4.10	35.00	0.10	0.00	f	Artisan beer with distinctive character and flavor.
994	Dead Frog Brewing 24-pack	Craft Beer	204.00	50	\N	/data/product_images/994_Dead_Frog_Brewing_24-pack.jpg	2026-01-07 18:25:13.642262	151.11	35.00	2.40	0.00	f	Artisan beer with distinctive character and flavor.
995	Dead Frog Brewing 6-pack	Craft Beer	51.00	50	\N	/data/product_images/995_Dead_Frog_Brewing_6-pack.jpg	2026-01-07 18:25:13.642262	37.78	35.00	0.60	0.00	f	Artisan beer with distinctive character and flavor.
996	Strongbow 355ml	Ciders	3.75	50	\N	/data/product_images/996_Strongbow_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
997	Strongbow 473ml	Ciders	4.88	50	\N	/data/product_images/997_Strongbow_473ml.jpg	2026-01-07 18:25:13.644819	3.61	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
998	Strongbow 24-pack	Ciders	180.00	50	\N	/data/product_images/998_Strongbow_24-pack.jpg	2026-01-07 18:25:13.644819	133.33	35.00	2.40	0.00	f	Cider. Fruity, refreshing alternative to beer.
999	Woodchuck 355ml	Ciders	3.75	50	\N	/data/product_images/999_Woodchuck_355ml.jpg	2026-01-07 18:25:13.644819	2.78	35.00	0.10	0.00	f	Cider. Fruity, refreshing alternative to beer.
99	Jameson 1L	Whiskey	39.54	50	\N	/data/product_images/99_Jameson_1L.jpg	2026-01-07 18:24:49.609209	29.29	35.00	0.10	0.00	f	Irish whiskey with triple distillation. Smooth, sweet, triple pot still character.
\.


--
-- Name: beverage_products_item_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.beverage_products_item_id_seq', 1069, true);


--
-- Name: beverage_products beverage_products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.beverage_products
    ADD CONSTRAINT beverage_products_pkey PRIMARY KEY (item_id);


--
-- PostgreSQL database dump complete
--

\unrestrict 1xhI45hUeHzkBYHBbCSiqKZ8OeFvp0JUqpn6QJVas09tMCnSV2WU3mmH4hMcCOM

