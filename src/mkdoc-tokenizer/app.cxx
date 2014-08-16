/* -*- coding: utf-8; mode: c++; tab-width: 3; indent-tabs-mode: nil -*-

Copyright 2014
Raffaello D. Di Napoli

This file is part of Abaclade.

Abaclade is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

Abaclade is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along with Abaclade. If not, see
<http://www.gnu.org/licenses/>.
--------------------------------------------------------------------------------------------------*/

#include <abaclade.hxx>
#include <abaclade/app.hxx>
#include <abaclade/io/text/file.hxx>
using namespace abc;



////////////////////////////////////////////////////////////////////////////////////////////////////
// mkdoc_tokenizer_app


/** Characer types. Used to group evolutions by character type, to avoid repetitions: for example,
all evolutions for ‘A’ will always apply to ‘B’.
*/
ABC_ENUM(char_type,
   /** Backslash. */
   (bksl,   0),
   /** Decimal digit. */
   (digit,  1),
   /** Dot. */
   (dot,    2),
   /** End-of-line character. */
   (eol,    3),
   /** Forward slash. */
   (fwsl,   4),
   /** Invalid character that can only appear in literals. */
   (inval,  5),
   /** Letter. */
   (ltr,    6),
   /** Letter ‘e’ or ‘E’. */
   (ltre,   7),
   /** Minus sign/hyphen. */
   (minus,  8),
   /** Plus sign. */
   (plus,   9),
   /** Pound sign/hash. */
   (pound, 10),
   /** Punctuation. */
   (punct, 11),
   /** Double quotes. */
   (qdbl,  12),
   /** Single quote. */
   (qsng,  13),
   /** Star/asterisk. */
   (star,  14),
   /** Whitespace. */
   (whsp,  15),
   /** Count of char_types. */
   (count, 16)
);

/** Mapping from character values to character types. */
static char_type::enum_type const chtMap[128] = {
#define T char_type::
   /*00 */T inval, /*01 */T inval, /*02 */T inval, /*03 */T inval, /*04 */T inval, /*05 */T inval,
   /*06 */T inval, /*\a */T inval, /*08 */T inval, /*\t */T whsp , /*\n */T eol  , /*\v */T whsp ,
   /*\f */T whsp , /*\r */T whsp , /*0e */T inval, /*0f */T inval, /*10 */T inval, /*11 */T inval,
   /*12 */T inval, /*13 */T inval, /*14 */T inval, /*15 */T inval, /*16 */T inval, /*17 */T inval,
   /*18 */T inval, /*19 */T inval, /*0a */T inval, /*\e */T inval, /*1c */T inval, /*1d */T inval,
   /*1e */T inval, /*1f */T inval, /*sp */T whsp , /* ! */T punct, /* " */T qdbl , /* # */T pound,
   /* $ */T inval, /* % */T punct, /* & */T punct, /* ' */T qsng , /* ( */T punct, /* ) */T punct,
   /* * */T star , /* + */T plus , /* , */T punct, /* - */T minus, /* . */T dot  , /* / */T fwsl ,
   /* 0 */T digit, /* 1 */T digit, /* 2 */T digit, /* 3 */T digit, /* 4 */T digit, /* 5 */T digit,
   /* 6 */T digit, /* 7 */T digit, /* 8 */T digit, /* 9 */T digit, /* : */T punct, /* ; */T punct,
   /* < */T punct, /* = */T punct, /* > */T punct, /* ? */T punct, /* @ */T inval, /* A */T ltr  ,
   /* B */T ltr  , /* C */T ltr  , /* D */T ltr  , /* E */T ltre , /* F */T ltr  , /* G */T ltr  ,
   /* H */T ltr  , /* I */T ltr  , /* J */T ltr  , /* K */T ltr  , /* L */T ltr  , /* M */T ltr  ,
   /* N */T ltr  , /* O */T ltr  , /* P */T ltr  , /* Q */T ltr  , /* R */T ltr  , /* S */T ltr  ,
   /* T */T ltr  , /* U */T ltr  , /* V */T ltr  , /* W */T ltr  , /* X */T ltr  , /* Y */T ltr  ,
   /* Z */T ltr  , /* [ */T punct, /* \ */T bksl , /* ] */T punct, /* ^ */T punct, /* _ */T ltr  ,
   /* ` */T inval, /* a */T ltr  , /* b */T ltr  , /* c */T ltr  , /* d */T ltr  , /* e */T ltre ,
   /* f */T ltr  , /* g */T ltr  , /* h */T ltr  , /* i */T ltr  , /* j */T ltr  , /* k */T ltr  ,
   /* l */T ltr  , /* m */T ltr  , /* n */T ltr  , /* o */T ltr  , /* p */T ltr  , /* q */T ltr  ,
   /* r */T ltr  , /* s */T ltr  , /* t */T ltr  , /* u */T ltr  , /* v */T ltr  , /* w */T ltr  ,
   /* x */T ltr  , /* y */T ltr  , /* z */T ltr  , /* { */T punct, /* | */T punct, /* } */T punct,
   /* ~ */T punct, /*7f */T inval
#undef T
};

/** Tokenizer state. */
ABC_ENUM(state,
   /** Found a single backslash. */
   (bksl,   0),
   /** Found a single backslash that may need to be accumulated in the current token. */
   (bsac,   1),
   /** Start of a new, non-continued line. This is the initial (BOF) state. */
   (bol,    2),
   /** Single-quoted character literal. */
   (cl,     3),
   /** Single-quoted character literal, after the closing single-quote. */
   (cle,    4),
   /** Multi-line comment. */
   (cmm,    5),
   /** Multi-line comment, after a star (potential terminator sequence start). */
   (cmms,   6),
   /** Single-line comment. */
   (cms,    7),
   /** C preprocessor directive. */
   (cpp,    8),
   /** Single dot. */
   (dot,    9),
   /** Two dots. */
   (dot2,  10),
   /** Found a single forward slash. */
   (fwsl,  11),
   /** Generic token. Default state others go to when their tokens are finished. */
   (gen,   12),
   /** Identifier. */
   (id,    13),
   /** Minus sign. */
   (mns,   14),
   /** Number. */
   (num,   15),
   /** Number followed by ‘e’ or ‘E’ (could be suffix or exponent). */
   (nume,  16),
   /** Suffix following a number, or exponent of a number. */
   (nums,  17),
   /** Plus sign. */
   (pls,   18),
   /** Double-quoted string literal. */
   (sl,    19),
   /** Double-quoted string literal, after the closing double-quote. */
   (sle,   20),
   /** Whitespace run, */
   (whsp,  21),
   /** Count of states. */
   (count, 22),
   /** Error; will cause the tokenizer to stop. */
   (err,   22)
);

/** Tokenizer action. */
ABC_ENUM(action,
   /** Accumulate the character into the current token. */
   (acc, 0),
   /** Error; will cause the tokenizer to stop. */
   (err, 1),
   /** Output the current token, then start a new one, ignoring the current character. */
   (out, 2),
   /** Output the current token, then start a new one accumulating the current character into it. */
   (o_a, 3),
   /** Pushe the current state into the state stack. */
   (sps, 4),
   /** Pop from the state stack into the current state. */
   (spp, 5),
   /** Pop from the state stack into the current state, accumulating a backslash and the current
   character into the current token. */
   (spb, 6)
);

/** Tokenizer evolution. */
struct evo_t {
   state::enum_type stateNext;
   action::enum_type actionNext;
};

/** Tokenizer evolutions: map from (state, char_type) to (state, action). */
static evo_t const evos[state::count][char_type::count] = {
#define E(s, a) { state::s, action::a }
   /*        bksl        digit       dot         eol         fwsl        inval       ltr         ltre        minus       plus        pound       punct       qdbl        qsng        star        whsp       */
   /*bksl*/ {E(err ,err),E(err ,err),E(err ,err),E(bksl,spp),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err)},
   /*bsac*/ {E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spp),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb)},
   /*bol */ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(cpp ,o_a),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(bol ,out)},
   /*cl  */ {E(bsac,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cle ,acc),E(cl  ,acc),E(cl  ,acc)},
   /*cle */ {E(bksl,sps),E(cle ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(cle ,acc),E(cle ,acc),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*cmm */ {E(bksl,sps),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(err ,err),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmms,acc),E(cmm ,acc)},
   /*cmms*/ {E(bksl,sps),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(fwsl,acc),E(err ,err),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmms,acc),E(cmm ,acc)},
   /*cms */ {E(bksl,sps),E(cms ,acc),E(cms ,acc),E(bol ,out),E(cms ,acc),E(err ,err),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc)},
   /*cpp */ {E(bksl,sps),E(cpp ,acc),E(cpp ,acc),E(bol ,out),E(cpp ,acc),E(err ,err),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc)},
   /*dot */ {E(bksl,sps),E(num ,acc),E(dot2,acc),E(bol ,out),E(fwsl,o_a),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(mns ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*dot2*/ {E(bksl,sps),E(err ,err),E(gen ,acc),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err),E(err ,err)},
   /*fwsl*/ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(cms ,acc),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(cmm ,acc),E(whsp,o_a)},
   /*gen */ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*id  */ {E(bksl,sps),E(id  ,acc),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(id  ,acc),E(id  ,acc),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*mns */ {E(bksl,sps),E(num ,acc),E(num ,acc),E(bol ,out),E(fwsl,o_a),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(gen ,acc),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*num */ {E(bksl,sps),E(num ,acc),E(num ,acc),E(bol ,out),E(fwsl,o_a),E(err ,err),E(nums,acc),E(nume,acc),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*nume*/ {E(bksl,sps),E(nums,acc),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(nums,acc),E(nums,acc),E(nums,acc),E(nums,acc),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*nums*/ {E(bksl,sps),E(nums,acc),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(nums,acc),E(nums,acc),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*pls */ {E(bksl,sps),E(num ,o_a),E(num ,acc),E(bol ,out),E(fwsl,o_a),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(gen ,acc),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*sl  */ {E(bsac,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sle ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc)},
   /*sle */ {E(bksl,sps),E(sle ,o_a),E(dot ,o_a),E(bol ,out),E(fwsl,o_a),E(err ,err),E(sle ,acc),E(sle ,acc),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,o_a)},
   /*whsp*/ {E(bksl,sps),E(num ,o_a),E(dot ,o_a),E(bol ,acc),E(fwsl,o_a),E(err ,err),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(pls ,o_a),E(err ,err),E(gen ,o_a),E(sl  ,o_a),E(cl  ,o_a),E(gen ,o_a),E(whsp,acc)}
#undef E
};

/** Possible output token types. */
ABC_ENUM(token_type,
   (ampers,     0),
   (bkslash,    1),
   (bracel,     2),
   (bracer,     3),
   (bracketl,   4),
   (bracketr,   5),
   (caret,      6),
   (chrlit,     7),
   (colon,      8),
   (comma,      9),
   (cpreproc,  10),
   (ellipsis,  11),
   (dot,       12),
   (equal,     13),
   (excl,      14),
   (fwdslash,  15),
   (gt,        16),
   (ident,     17),
   (less,      18),
   (minus,     19),
   (number,    20),
   (parenl,    21),
   (parenr,    22),
   (percent,   23),
   (pipe,      24),
   (plus,      25),
   (semicol,   26),
   (strlit,    27),
   (tilde,     28),
   (whitesp,   29)
);

/** Tokens output by each state when the evolution’s action is “output”. */
static token_type const ttStateOutputs[state::count] = {
#define T token_type::
#undef T
};

class mkdoc_tokenizer_app :
   public app {
public:

   /** See app::main().
   */
   virtual int main(mvector<istr const> const & vsArgs) {
      ABC_TRACE_FUNC(this, vsArgs);

      dmstr sAll;
      io::text::open_reader(dmstr(ABC_SL("include/abaclade/enum.hxx")))->read_all(&sAll);
      tokenize(sAll);

      return 0;
   }


   /** TODO: comment.
   */
   static void tokenize(istr const & sAll) {
      auto ftwErr(io::text::stderr());

      state stateCurr(state::bol);
      smstr<256> sCurrToken;
      state statePushed;
      for (auto it(sAll.cbegin()); it != sAll.cend(); ++it) {
         char32_t ch(*it);
         // Determine the type of the current character.
         char_type cht;
         if (static_cast<size_t>(ch) < ABC_COUNTOF(chtMap)) {
            cht = chtMap[static_cast<uint8_t>(ch)];
         } else {
            cht = char_type::ltr;
         }

         evo_t const & evo(evos[stateCurr.base()][cht.base()]);
         /*ftwErr->print(
            ABC_SL("evolution: (state: {}, char_type: {} ‘{}’) -> (state: {}, action: {})\n"),
            stateCurr, cht, ch, state(evo.stateNext), action(evo.actionNext)
         );*/

         switch (evo.actionNext) {
            case action::err:
               // Error; will cause the tokenizer to stop.
               ftwErr->write_line(ABC_SL("ERROR"));
               return;
            case action::out:
            case action::o_a:
               if (sCurrToken) {
                  ftwErr->print(ABC_SL("token: {}\n"), sCurrToken);
               }
               sCurrToken = ABC_SL("");
               if (evo.actionNext != action::o_a) {
                  break;
               }
               // Fall through.
            case action::acc:
               // Accumulate the character into the current token.
               sCurrToken += ch;
               break;
            case action::sps:
               // Pushe the current state into the state stack.
               statePushed = stateCurr;
               break;
            case action::spp:
            case action::spb:
               // Pop from the state stack into the current state.
               stateCurr = statePushed;
               if (evo.actionNext == action::spb) {
                  // Accumulate a backslash and the current character into the current token.
                  sCurrToken += '\\';
                  sCurrToken += ch;
               }
               continue;
         }
         stateCurr = evo.stateNext;
      }
   }
};

ABC_APP_CLASS(mkdoc_tokenizer_app)

