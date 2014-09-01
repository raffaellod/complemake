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
#define AC(next) { tokenizer_state::next, tokenizer_action::accumulate }
#define ER()     { tokenizer_state::whsp, tokenizer_action::error }
#define PS(next) { tokenizer_state::next, tokenizer_action::push_state }
#define PP(next) { tokenizer_state::next, tokenizer_action::pop_state }
#define PB(next) { tokenizer_state::next, tokenizer_action::pop_state_and_accumulate_backslash }
#define YA(next) { tokenizer_state::next, tokenizer_action::yield_and_accumulate }
#define YI(next) { tokenizer_state::next, tokenizer_action::yield_and_ignore }
   /*        amp      aster    bksl     caret    colon    digit    dot      eol      equal    excl     fwsl     gt       inval    lt       ltr      ltre     minus    perc     pipe     plus     pound    punct    qdbl     qsng     tilde    whsp             */
   /*amp */ {AC(amp2),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*amp */
   /*amp2*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*amp2*/
   /*arw */ {YA(amp ),AC(arwa),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*arw */
   /*arwa*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*arw */
   /*astr*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*astr*/
   /*bksl*/ {ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),PP(bksl),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    )}, /*bksl*/
   /*bsac*/ {PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PP(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac),PB(bsac)}, /*bsac*/
   /*bol */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),YA(cpp ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YI(bol )}, /*bol */
   /*cl  */ {AC(cl  ),AC(cl  ),AC(bsac),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cl  ),AC(cle ),AC(cl  ),AC(cl  )}, /*cl  */
   /*cle */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(cle ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),AC(cle ),AC(cle ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*cle */
   /*cln */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),AC(cln2),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*cln */
   /*cln2*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*cln2*/
   /*cmm */ {AC(cmm ),AC(cmms),PS(bksl),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),ER(    ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm )}, /*cmm */
   /*cmms*/ {AC(cmm ),AC(cmms),PS(bksl),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmmz),AC(cmm ),ER(    ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm ),AC(cmm )}, /*cmms*/
   /*cmmz*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),AC(cmmz)}, /*cmmz*/
   /*cms */ {AC(cms ),AC(cms ),PS(bksl),AC(cms ),AC(cms ),AC(cms ),AC(cms ),YI(bol ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),ER(    ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms ),AC(cms )}, /*cms */
   /*cpp */ {AC(cpp ),AC(cpp ),PS(bksl),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),YI(bol ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),ER(    ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp ),AC(cpp )}, /*cpp */
   /*crt */ {YA(amp ),YA(astr),PS(bksl),AC(crt2),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*crt */
   /*crt2*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*crt2*/
   /*dot */ {YA(amp ),AC(dota),PS(bksl),YA(crt ),YA(cln ),AC(num ),AC(dot2),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(mns ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*dot */
   /*dot2*/ {ER(    ),ER(    ),PS(bksl),ER(    ),ER(    ),ER(    ),AC(dot3),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    ),ER(    )}, /*dot2*/
   /*dot3*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(mns ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*dot3*/
   /*dota*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(num ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*dota*/
   /*eql */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*eql */
   /*excl*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*excl*/
   /*fwsl*/ {YA(amp ),AC(cmm ),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),AC(cms ),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*fwsl*/
   /*gt  */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),AC(gt2 ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*gt  */
   /*gt2 */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*gt2 */
   /*id  */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),AC(id  ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),AC(id  ),AC(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*id  */
   /*lt  */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),AC(lt2 ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*lt  */
   /*lt2 */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*lt2 */
   /*mns */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),AC(num ),AC(num ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),AC(arw ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),AC(mns2),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*mns */
   /*mns2*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(num ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*mns2*/
   /*num */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),AC(num ),AC(num ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),AC(nums),AC(nume),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*num */
   /*nume*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),AC(nums),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),AC(nums),AC(nums),AC(nums),YA(perc),YA(pip ),AC(nums),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*nume*/
   /*nums*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),AC(nums),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),AC(nums),AC(nums),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*nums*/
   /*opeq*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*opeq*/
   /*perc*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*perc*/
   /*pip */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),AC(pip2),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*pip */
   /*pip2*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*pip2*/
   /*pls */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),AC(num ),AC(num ),YI(bol ),AC(opeq),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),AC(pls2),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*pls */
   /*pls2*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(num ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*pls2*/
   /*punc*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*punc*/
   /*sl  */ {AC(sl  ),AC(sl  ),AC(bsac),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sl  ),AC(sle ),AC(sl  ),AC(sl  ),AC(sl  )}, /*sl  */
   /*sle */ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(sle ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),AC(sle ),AC(sle ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*sle */
   /*tild*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),YA(whsp)}, /*tild*/
   /*whsp*/ {YA(amp ),YA(astr),PS(bksl),YA(crt ),YA(cln ),YA(num ),YA(dot ),YI(bol ),YA(eql ),YA(excl),YA(fwsl),YA(gt  ),ER(    ),YA(lt  ),YA(id  ),YA(id  ),YA(mns ),YA(perc),YA(pip ),YA(pls ),ER(    ),YA(punc),YA(sl  ),YA(cl  ),YA(tild),AC(whsp)}  /*whsp*/
#undef AC
#undef ER
#undef PS
#undef PP
#undef PB
#undef YA
#undef YI
};

token_iterator::output_token_t const token_iterator::smc_ttStateOutputs[
   tokenizer_state::size_const
] = {
#define OF(fixed)   { nullptr, token_type::fixed }
#define OS(special) { &token_iterator::special, token_type::error }
   /* amp  */ OF(ampersand),
   /* amp2 */ OF(op_log_and),
   /* arw  */ OF(op_deref_member_access),
   /* arwa */ OF(op_ptr_to_member_deref_ptr),
   /* astr */ OF(asterisk),
   /* bksl */ OF(error),
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
   /* crt  */ OF(op_bit_xor),
   /* crt2 */ OF(op_log_xor),
   /* dot  */ OF(dot),
   /* dot2 */ OF(error),
   /* dot3 */ OF(ellipsis),
   /* dota */ OF(op_ptr_to_member_deref_val),
   /* eql  */ OF(assign),
   /* excl */ OF(op_log_not),
   /* fwsl */ OF(op_div),
   /* gt   */ OF(op_rel_gt),
   /* gt2  */ OF(op_rsh),
   /* id   */ OF(identifier),
   /* lt   */ OF(op_rel_lt),
   /* lt2  */ OF(op_lsh),
   /* mns  */ OF(minus),
   /* mns2 */ OF(op_decr),
   /* num  */ OF(number),
   /* nume */ OF(number),
   /* nums */ OF(number),
   /* opeq */ OS(get_compound_assignm_token_type),
   /* perc */ OF(op_mod),
   /* pip  */ OF(op_bit_or),
   /* pip2 */ OF(op_log_or),
   /* pls  */ OF(plus),
   /* pls2 */ OF(op_incr),
   /* punc */ OS(get_punctuation_token_type),
   /* sl   */ OF(error),
   /* sle  */ OF(stringlit),
   /* tild */ OF(op_bit_not),
   /* whsp */ OF(whitesp)
#undef OF
#undef OS
};

token_iterator const token_iterator::smc_itEnd((token_type(token_type::end)));


/*explicit*/ token_iterator::token_iterator(mstr && sAll) :
   m_sAll(std::move(sAll)),
   m_itAllCurr(m_sAll.cbegin()),
   m_stateCurr(tokenizer_state::bol) {
   // Find the first token.
   operator++();
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
         case tokenizer_action::yield_and_accumulate:
         case tokenizer_action::yield_and_ignore:
            if (m_tkNext.m_s) {
               finalize_next_token();
               bYield = true;
            }
            if (evo.actionNext == tokenizer_action::yield_and_ignore) {
               break;
            }
            // Fall through.
         case tokenizer_action::accumulate:
            // Accumulate the character into the current token.
            m_tkNext.m_s += ch;
            break;
         case tokenizer_action::error:
            // Error; will cause the tokenizer to stop.
            ftwErr->write_line(ABC_SL("ERROR"));
            bYield = true;
            break;
         case tokenizer_action::pop_state:
         case tokenizer_action::pop_state_and_accumulate_backslash:
            // Pop from the state stack into the current state.
            m_stateCurr = statePushed;
            if (evo.actionNext == tokenizer_action::pop_state_and_accumulate_backslash) {
               // Accumulate a backslash and the current character into the current token.
               m_tkNext.m_s += '\\';
               m_tkNext.m_s += ch;
            }
            // We already selected the next state, skip the last line in the loop.
            continue;
         case tokenizer_action::push_state:
            statePushed = m_stateCurr;
            break;
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


void token_iterator::get_compound_assignm_token_type() {
   char ch0(static_cast<char>(m_tkNext.m_s[0]));
   switch (ch0) {
      case '!': m_tkNext.m_tt = token_type::op_rel_noteq;      break;
      case '%': m_tkNext.m_tt = token_type::op_mod_assign;     break;
      case '&': m_tkNext.m_tt = token_type::op_bit_and_assign; break;
      case '*': m_tkNext.m_tt = token_type::op_mult_assign;    break;
      case '+': m_tkNext.m_tt = token_type::op_add_assign;     break;
      case '-': m_tkNext.m_tt = token_type::op_sub_assign;     break;
      case '/': m_tkNext.m_tt = token_type::op_div_assign;     break;
      case '=': m_tkNext.m_tt = token_type::op_rel_equal;      break;
      case '^': m_tkNext.m_tt = token_type::op_bit_xor_assign; break;
      case '|': m_tkNext.m_tt = token_type::op_bit_or_assign;  break;
      case '<':
      case '>':
         if (static_cast<char>(m_tkNext.m_s[1]) == ch0) {
            // “<<=” or “>>=”.
            m_tkNext.m_tt = ch0 == '<' ? token_type::op_lsh_assign : token_type::op_rsh_assign;
         } else {
            // “<=” or “>=”.
            m_tkNext.m_tt = ch0 == '<' ? token_type::op_rel_lteq : token_type::op_rel_gteq;
         }
         break;
   }
}


void token_iterator::get_cpreproc_token_type() {
   // TODO
}


void token_iterator::get_punctuation_token_type() {
   switch (static_cast<char>(m_tkNext.m_s[0])) {
      case '(': m_tkNext.m_tt = token_type::parenl;    break;
      case ')': m_tkNext.m_tt = token_type::parenr;    break;
      case ',': m_tkNext.m_tt = token_type::comma;     break;
      case ';': m_tkNext.m_tt = token_type::semicolon; break;
      case '?': m_tkNext.m_tt = token_type::qmark;     break;
      case '[': m_tkNext.m_tt = token_type::bracketl;  break;
      case ']': m_tkNext.m_tt = token_type::bracketr;  break;
      case '{': m_tkNext.m_tt = token_type::bracel;    break;
      case '}': m_tkNext.m_tt = token_type::bracer;    break;
   }
}

