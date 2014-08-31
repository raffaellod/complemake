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
using namespace abc;

#include "tokenizer.hxx"



////////////////////////////////////////////////////////////////////////////////////////////////////
// token_iterator


char_type::enum_type const token_iterator::smc_chtMap[128] = {
#define T char_type::
   /*00 */T inval, /*01 */T inval, /*02 */T inval, /*03 */T inval, /*04 */T inval, /*05 */T inval,
   /*06 */T inval, /*\a */T inval, /*08 */T inval, /*\t */T whsp , /*\n */T eol  , /*\v */T whsp ,
   /*\f */T whsp , /*\r */T whsp , /*0e */T inval, /*0f */T inval, /*10 */T inval, /*11 */T inval,
   /*12 */T inval, /*13 */T inval, /*14 */T inval, /*15 */T inval, /*16 */T inval, /*17 */T inval,
   /*18 */T inval, /*19 */T inval, /*0a */T inval, /*\e */T inval, /*1c */T inval, /*1d */T inval,
   /*1e */T inval, /*1f */T inval, /*sp */T whsp , /* ! */T excl , /* " */T qdbl , /* # */T pound,
   /* $ */T inval, /* % */T perc , /* & */T amp  , /* ' */T qsng , /* ( */T punct, /* ) */T punct,
   /* * */T aster, /* + */T plus , /* , */T punct, /* - */T minus, /* . */T dot  , /* / */T fwsl ,
   /* 0 */T digit, /* 1 */T digit, /* 2 */T digit, /* 3 */T digit, /* 4 */T digit, /* 5 */T digit,
   /* 6 */T digit, /* 7 */T digit, /* 8 */T digit, /* 9 */T digit, /* : */T colon, /* ; */T punct,
   /* < */T lt   , /* = */T equal, /* > */T gt   , /* ? */T punct, /* @ */T inval, /* A */T ltr  ,
   /* B */T ltr  , /* C */T ltr  , /* D */T ltr  , /* E */T ltre , /* F */T ltr  , /* G */T ltr  ,
   /* H */T ltr  , /* I */T ltr  , /* J */T ltr  , /* K */T ltr  , /* L */T ltr  , /* M */T ltr  ,
   /* N */T ltr  , /* O */T ltr  , /* P */T ltr  , /* Q */T ltr  , /* R */T ltr  , /* S */T ltr  ,
   /* T */T ltr  , /* U */T ltr  , /* V */T ltr  , /* W */T ltr  , /* X */T ltr  , /* Y */T ltr  ,
   /* Z */T ltr  , /* [ */T punct, /* \ */T bksl , /* ] */T punct, /* ^ */T caret, /* _ */T ltr  ,
   /* ` */T inval, /* a */T ltr  , /* b */T ltr  , /* c */T ltr  , /* d */T ltr  , /* e */T ltre ,
   /* f */T ltr  , /* g */T ltr  , /* h */T ltr  , /* i */T ltr  , /* j */T ltr  , /* k */T ltr  ,
   /* l */T ltr  , /* m */T ltr  , /* n */T ltr  , /* o */T ltr  , /* p */T ltr  , /* q */T ltr  ,
   /* r */T ltr  , /* s */T ltr  , /* t */T ltr  , /* u */T ltr  , /* v */T ltr  , /* w */T ltr  ,
   /* x */T ltr  , /* y */T ltr  , /* z */T ltr  , /* { */T punct, /* | */T pipe , /* } */T punct,
   /* ~ */T tilde, /*7f */T inval
#undef T
};

token_iterator::evo_t const token_iterator::smc_evos
   [tokenizer_state::size_const][char_type::size_const] = {
#define E(s, a) { tokenizer_state::s, tokenizer_action::a }
   /*        amp         aster       bksl        caret       colon       digit       dot         eol         equal       excl        fwsl        gt          inval       lt          ltr         ltre        minus       perc        pipe        plus        pound       punct       qdbl        qsng        tilde       whsp       */
   /*amp  */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*astr */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*bksl*/ {E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,spp),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err),E(bksl,err)},
   /*bsac*/ {E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spp),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb),E(bsac,spb)},
   /*bol */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(bol ,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(cpp ,o_a),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(bol ,out)},
   /*cl  */ {E(cl  ,acc),E(cl  ,acc),E(bsac,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cl  ,acc),E(cle ,acc),E(cl  ,acc),E(cl  ,acc)},
   /*cle */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(cle ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(cle ,err),E(lt  ,o_a),E(cle ,acc),E(cle ,acc),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(cle ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*cln */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln2,acc),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(cln ,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(cln ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*cln2*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(cln2,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(cln2,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*cmm */ {E(cmm ,acc),E(cmms,acc),E(bksl,sps),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,err),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc)},
   /*cmms*/ {E(cmm ,acc),E(cmms,acc),E(bksl,sps),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmmz,acc),E(cmm ,acc),E(cmms,err),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc),E(cmm ,acc)},
   /*cmmz*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(cmmz,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(cmmz,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(cmmz,acc)},
   /*cms */ {E(cms ,acc),E(cms ,acc),E(bksl,sps),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(bol ,out),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,err),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc),E(cms ,acc)},
   /*cpp */ {E(cpp ,acc),E(cpp ,acc),E(bksl,sps),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(bol ,out),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,err),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc),E(cpp ,acc)},
   /*crt  */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*dot */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,acc),E(dot2,acc),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(dot ,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(mns ,o_a),E(dot ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*dot2*/ {E(dot2,err),E(dot2,err),E(bksl,sps),E(dot2,err),E(dot2,err),E(dot2,err),E(dot3,acc),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err),E(dot2,err)},
   /*dot3*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(dot3,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(mns ,o_a),E(dot3,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*eql  */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*excl */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*fwsl*/ {E(amp ,o_a),E(cmm ,acc),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(cms ,acc),E(gt  ,o_a),E(fwsl,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(fwsl,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*gt   */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*id  */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(id  ,acc),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(id  ,err),E(lt  ,o_a),E(id  ,acc),E(id  ,acc),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(id  ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*lt   */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*mns */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,acc),E(num ,acc),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(mns ,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns2,acc),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(mns ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*mns2*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(num ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(mns2,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(mns2,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*num */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,acc),E(num ,acc),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(num ,err),E(lt  ,o_a),E(nums,acc),E(nume,acc),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(num ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*nume*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(nums,acc),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(nume,err),E(lt  ,o_a),E(nums,acc),E(nums,acc),E(nums,acc),E(perc,o_a),E(pip ,o_a),E(nums,acc),E(nume,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*nums*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(nums,acc),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(nums,err),E(lt  ,o_a),E(nums,acc),E(nums,acc),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(nums,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*perc */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*pip  */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*pls */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,acc),E(num ,acc),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(pls ,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls2,acc),E(pls ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*pls2*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(num ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(pls2,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(pls2,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*punc*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*sl  */ {E(sl  ,acc),E(sl  ,acc),E(bsac,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc),E(sle ,acc),E(sl  ,acc),E(sl  ,acc),E(sl  ,acc)},
   /*sle */ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(sle ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(sle ,err),E(lt  ,o_a),E(sle ,acc),E(sle ,acc),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(sle ,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*tild */{E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(punc,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(punc,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,o_a)},
   /*whsp*/ {E(amp ,o_a),E(astr,o_a),E(bksl,sps),E(crt ,o_a),E(cln ,o_a),E(num ,o_a),E(dot ,o_a),E(bol ,out),E(eql ,o_a),E(excl,o_a),E(fwsl,o_a),E(gt  ,o_a),E(whsp,err),E(lt  ,o_a),E(id  ,o_a),E(id  ,o_a),E(mns ,o_a),E(perc,o_a),E(pip ,o_a),E(pls ,o_a),E(whsp,err),E(punc,o_a),E(sl  ,o_a),E(cl  ,o_a),E(tild,o_a),E(whsp,acc)}
#undef E
};

token_iterator::output_token_t const token_iterator::smc_ttStateOutputs[tokenizer_state::size_const] = {
#define OF(fixed)   { nullptr, token_type::fixed }
#define OS(special) { &token_iterator::special, token_type::error }
   /* amp  */ OF(ampersand),
   /* astr */ OF(asterisk),
   /* bksl */ OF(backslash),
   /* bsac */ OF(error),
   /* bol  */ OF(error),
   /* cl   */ OF(error),
   /* cle  */ OF(charlit),
   /* cln  */ OF(colon),
   /* cln2 */ OF(dbl_colon),
   /* cmm  */ OF(error),
   /* cmms */ OF(error),
   /* cmmz */ OS(get_comment_token_type),
   /* cms  */ OS(get_comment_token_type),
   /* cpp  */ OS(get_cpreproc_token_type),
   /* crt  */ OF(caret),
   /* dot  */ OF(dot),
   /* dot2 */ OF(error),
   /* dot3 */ OF(ellipsis),
   /* eql  */ OF(rel_equal),
   /* excl */ OF(exclam),
   /* fwsl */ OF(fwdslash),
   /* gt   */ OF(rel_gt),
   /* id   */ OF(ident),
   /* lt   */ OF(rel_lt),
   /* mns  */ OF(minus),
   /* mns2 */ OF(decr),
   /* num  */ OF(number),
   /* nume */ OF(number),
   /* nums */ OF(number),
   /* perc */ OF(percent),
   /* pip  */ OF(pipe),
   /* pls  */ OF(plus),
   /* pls2 */ OF(incr),
   /* punc */ OS(get_punctuation_token_type),
   /* sl   */ OF(error),
   /* sle  */ OF(stringlit),
   /* tild */ OF(tilde),
   /* whsp */ OF(whitesp)
#undef OF
#undef OS
};


/*explicit*/ token_iterator::token_iterator(mstr && sAll) :
   m_sAll(std::move(sAll)),
   m_itAllCurr(m_sAll.cbegin()),
   m_stateCurr(tokenizer_state::bol) {
}


token_iterator & token_iterator::operator++() {
   auto ftwErr(io::text::stderr());

   tokenizer_state statePushed;
   bool bYield(false);
   while (m_itAllCurr != m_sAll.cend() && !bYield) {
      char32_t ch(*m_itAllCurr++);
      // Determine the type of the current character.
      char_type cht;
      if (static_cast<size_t>(ch) < ABC_COUNTOF(smc_chtMap)) {
         cht = smc_chtMap[static_cast<uint8_t>(ch)];
      } else {
         cht = char_type::ltr;
      }

      evo_t const & evo(smc_evos[m_stateCurr.base()][cht.base()]);
      /*ftwErr->print(
         ABC_SL("evolution: (state: {}, char_type: {} ‘{}’) -> (state: {}, action: {})\n"),
         m_stateCurr, cht, ch, tokenizer_state(evo.stateNext), tokenizer_action(evo.actionNext)
      );*/

      switch (evo.actionNext) {
         case tokenizer_action::err:
            // Error; will cause the tokenizer to stop.
            ftwErr->write_line(ABC_SL("ERROR"));
            bYield = true;
            break;
         case tokenizer_action::out:
         case tokenizer_action::o_a:
            if (m_tkNext.m_s) {
               finalize_next_token();
               bYield = true;
            }
            if (evo.actionNext != tokenizer_action::o_a) {
               break;
            }
            // Fall through.
         case tokenizer_action::acc:
            // Accumulate the character into the current token.
            m_tkNext.m_s += ch;
            break;
         case tokenizer_action::sps:
            // Pushe the current state into the state stack.
            statePushed = m_stateCurr;
            break;
         case tokenizer_action::spp:
         case tokenizer_action::spb:
            // Pop from the state stack into the current state.
            m_stateCurr = statePushed;
            if (evo.actionNext == tokenizer_action::spb) {
               // Accumulate a backslash and the current character into the current token.
               m_tkNext.m_s += '\\';
               m_tkNext.m_s += ch;
            }
            // We already selected the next state, skip the last line in the loop.
            continue;
      }
      m_stateCurr = evo.stateNext;
   }
   if (!bYield) {
      // Check for a final token to yield.
      if (m_tkNext.m_s) {
         finalize_next_token();
         bYield = true;
      } else {
         // Set *this to the “end” state.
         m_tkCurr.m_tt = token_type::end;
      }
   }
   return *this;
}


void token_iterator::finalize_next_token() {
   // Determine the output token type for the current final state.
   output_token_t const & ot(smc_ttStateOutputs[m_stateCurr.base()]);
   if (ot.pfnSpecialCase) {
      // Default the token type to catch bugs in the special-case functions.
      m_tkNext.m_tt = token_type::error;
      (this->*ot.pfnSpecialCase)();
   } else {
      m_tkNext.m_tt = ot.ttFixed;
   }
   // Move the resulting token into m_tkCurr.
   // TODO: lock m_tkCurr before writing to it.
   m_tkCurr = std::move(m_tkNext);
}


void token_iterator::get_comment_token_type() {
   // Check for “/*!” and “//!”.
   if (m_tkNext.m_s[2] == '!') {
      // Special documentation comment.
      m_tkNext.m_tt = token_type::document;
   } else {
      m_tkNext.m_tt = token_type::comment;
   }
}


void token_iterator::get_cpreproc_token_type() {
}


void token_iterator::get_punctuation_token_type() {
}


token_iterator const & token_end() {
   static token_iterator const sc_itEnd(token_type(token_type::end));
   return sc_itEnd;
}

